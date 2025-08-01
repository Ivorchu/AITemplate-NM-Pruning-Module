// SPDX-License-Identifier: MIT
// Copyright (c) 2018-2022, Advanced Micro Devices, Inc. All rights reserved.

#include <cstdlib>

#include "ck/ck.hpp"
#include "ck/tensor_operation/gpu/device/tensor_layout.hpp"
#include "ck/tensor_operation/gpu/device/gemm_specialization.hpp"
#include "ck/tensor_operation/gpu/device/impl/device_batched_gemm_softmax_gemm_permute_xdl_cshuffle.hpp"
#include "ck/library/tensor_operation_instance/add_device_operation_instance.hpp"

namespace ck {
namespace tensor_operation {
namespace device {
namespace instance {

using F16 = ck::half_t;
using F32 = float;

using Row = ck::tensor_layout::gemm::RowMajor;
using Col = ck::tensor_layout::gemm::ColumnMajor;

template <ck::index_t... Is>
using S = ck::Sequence<Is...>;

using PassThrough = ck::tensor_operation::element_wise::PassThrough;
using ScaleAdd    = ck::tensor_operation::element_wise::ScaleAdd;

static constexpr auto GemmDefault = ck::tensor_operation::device::GemmSpecialization::Default;
static constexpr auto GemmPadded  = ck::tensor_operation::device::GemmSpecialization::MNKOPadding;

static constexpr auto TensorDefault = ck::tensor_operation::device::TensorSpecialization::Default;

// c[g, m, n] = a[g, m, k] * b[g, n, k]
template <index_t NumDimG,
          index_t NumDimM,
          index_t NumDimN,
          index_t NumDimK,
          index_t NumDimO,
          MaskingSpecialization MaskingSpec>
using device_batched_gemm_bias_softmax_gemm_permute_xdl_cshuffle_f16_f16_f16_f16_gmk_gnk_gno_gmo_instances =
    std::tuple<
        // clang-format off
        // #############################################|  NumDimG| NumDimM| NumDimN| NumDimK| NumDimO| AData| B0Data| B1Data| CData|    Acc0BiasData| Acc1BiasData| AccData| CShuffle|           A|          B0|        Acc0|          B1|           C|           GEMM|   ATensorSpec|  B0TensorSpec|  B1TensorSpec|   CTensorSpec| NumGemmK| Block| Gemm01| Gemm0| Gemm0| Gemm1| Gemm1| AK1| BK1| B1K1| MPer| NPer| Gemm0| Gemm0| Gemm1|  ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockLds|  B0BlockTransfer| B0BlockTransfer| B0BlockTransfer| B0BlockTransfer| B0BlockTransfer| B0BlockTransfer| B0BlockLds|  B1BlockTransfer| B1BlockTransfer| B1BlockTransfer| B1BlockTransfer| B1BlockTransfer| B1BlockTransfer| B1BlockLds|    CShuffle|    CShuffle| CBlockTransferClusterLengths|  CBlockTransfer| MaskingSpec|
        // #############################################|         |        |        |        |        |  Type|   Type|   Type|  Type|            Type|         Type|    Type| DataType| Elementwise| Elementwise| Elementwise| Elementwise| Elementwise| Specialization|              |              |              |              | Prefetch|  Size|   MPer|  NPer|  KPer|  NPer|  KPer|    |    |     |  XDL|  XDL|  MXdl|  NXdl|  NXdl|   ThreadCluster|  ThreadCluster| SrcAccessOrder|   SrcVectorDim|      SrcScalar|      DstScalar| AddExtraM|    ThreadCluster|   ThreadCluster|  SrcAccessOrder|    SrcVectorDim|       SrcScalar|       DstScalar|  AddExtraN|    ThreadCluster|   ThreadCluster|  SrcAccessOrder|    SrcVectorDim|       SrcScalar|       DstScalar|  AddExtraN| MXdlPerWave| NXdlPerWave|         _MBlock_MWaveMPerXdl| ScalarPerVector|            |
        // #############################################|         |        |        |        |        |      |       |       |      |                |             |        |         |   Operation|   Operation|   Operation|   Operation|   Operation|               |              |              |              |              |    Stage|      |  Block| Block| Block| Block| Block|    |    |     |     |     |   Per|   Per|   Per| Lengths_K0_M_K1|   ArrangeOrder|               |               |      PerVector|   PerVector_K1|          |  Lengths_K0_N_K1|    ArrangeOrder|                |                |       PerVector|    PerVector_K1|           |  Lengths_K0_N_K1|    ArrangeOrder|                |                |       PerVector|    PerVector_K1|           |  PerShuffle|  PerShuffle|         _NBlock_NWaveNPerXdl|   _NWaveNPerXdl|            |
        // #############################################|         |        |        |        |        |      |       |       |      |                |             |        |         |            |            |            |            |            |               |              |              |              |              |         |      |       |      |      |      |      |    |    |     |     |     |  Wave|  Wave|  Wave|                |               |               |               |               |               |          |                 |                |                |                |                |                |           |                 |                |                |                |                |                |           |            |            |                             |                |            |
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    256,   128,    32,    64,    32,   8,   8,    2,   32,   32,     2,     4,     2,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S<16, 16, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    256,   128,    32,   128,    32,   8,   8,    2,   32,   32,     2,     4,     4,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
 #if CK_WORKAROUND_SWDEV_388832
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,   256,    32,    64,    32,   8,   8,    2,   32,   32,     1,     8,     2,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S<16, 16, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
 #endif
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,   256,    32,   128,    32,   8,   8,    2,   32,   32,     1,     8,     4,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,   128,    64,    64,    32,   8,   8,    2,   32,   32,     1,     4,     2,     S<8, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,     false,      S<8, 32, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,      false,     S<16, 16, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,   128,    32,    64,    32,   8,   8,    2,   32,   32,     1,     4,     2,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S<16, 16, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,   128,    64,   128,    32,   8,   8,    2,   32,   32,     1,     4,     4,     S<8, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,     false,      S<8, 32, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,      false,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,   128,    32,   128,    32,   8,   8,    2,   32,   32,     1,     4,     4,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,     64,   256,    32,   128,    32,   8,   8,    2,   16,   16,     1,    16,     8,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           8,               S<1, 16, 1,16>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,     64,   256,    32,    64,    32,   8,   8,    2,   16,   16,     1,    16,     4,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S<16, 16, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           4,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,     64,   256,    64,   128,    32,   8,   8,    2,   16,   16,     1,    16,     8,     S<8, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<8, 32, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           8,               S<1, 16, 1,16>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,    GemmDefault, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,     64,   256,    64,    64,    32,   8,   8,    2,   16,   16,     1,    16,     4,     S<8, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<8, 32, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S<16, 16, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           4,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        // Padded fallback kernel
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,     GemmPadded, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,   128,    64,   128,    32,   8,   8,    2,   32,   32,     1,     4,     4,     S<8, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,     false,      S<8, 32, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,      false,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>,
        DeviceBatchedGemmSoftmaxGemmPermute_Xdl_CShuffle<  NumDimG, NumDimM, NumDimN, NumDimK, NumDimO,   F16,    F16,    F16,   F16,  ck::Tuple<F16>,  ck::Tuple<>,     F32,      F16, PassThrough, PassThrough,    ScaleAdd, PassThrough, PassThrough,     GemmPadded, TensorDefault, TensorDefault, TensorDefault, TensorDefault,        1,   256,    128,    64,    32,   128,    32,   8,   8,    2,   32,   32,     1,     2,     4,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              8,              8,      true,      S<4, 64, 1>,      S<1, 0, 2>,      S<1, 0, 2>,               2,               8,               8,       true,     S< 8, 32, 1>,      S<0, 2, 1>,      S<0, 2, 1>,               1,               4,               2,      false,           1,           2,               S<1, 32, 1, 8>,               8, MaskingSpec>
        // clang-format on
        >;

void add_device_batched_gemm_bias_masking_softmax_gemm_permute_xdl_cshuffle_f16_f16_f16_f16_gmk_gnk_gno_gmo_instances(
    std::vector<std::unique_ptr<
        DeviceBatchedGemmSoftmaxGemmPermute<2,
                                            1,
                                            1,
                                            1,
                                            1,
                                            F16,
                                            F16,
                                            F16,
                                            F16,
                                            ck::Tuple<F16>,
                                            ck::Tuple<>,
                                            PassThrough,
                                            PassThrough,
                                            ScaleAdd,
                                            PassThrough,
                                            PassThrough,
                                            MaskingSpecialization::MaskOutUpperTriangle>>>&
        instances)
{
    add_device_operation_instances(
        instances,
        device_batched_gemm_bias_softmax_gemm_permute_xdl_cshuffle_f16_f16_f16_f16_gmk_gnk_gno_gmo_instances<
            2,
            1,
            1,
            1,
            1,
            MaskingSpecialization::MaskOutUpperTriangle>{});
}

void add_device_batched_gemm_bias_softmax_gemm_permute_xdl_cshuffle_f16_f16_f16_f16_gmk_gnk_gno_gmo_instances(
    std::vector<
        std::unique_ptr<DeviceBatchedGemmSoftmaxGemmPermute<2,
                                                            1,
                                                            1,
                                                            1,
                                                            1,
                                                            F16,
                                                            F16,
                                                            F16,
                                                            F16,
                                                            ck::Tuple<F16>,
                                                            ck::Tuple<>,
                                                            PassThrough,
                                                            PassThrough,
                                                            ScaleAdd,
                                                            PassThrough,
                                                            PassThrough,
                                                            MaskingSpecialization::MaskDisabled>>>&
        instances)
{
    add_device_operation_instances(
        instances,
        device_batched_gemm_bias_softmax_gemm_permute_xdl_cshuffle_f16_f16_f16_f16_gmk_gnk_gno_gmo_instances<
            2,
            1,
            1,
            1,
            1,
            MaskingSpecialization::MaskDisabled>{});
}

} // namespace instance
} // namespace device
} // namespace tensor_operation
} // namespace ck
