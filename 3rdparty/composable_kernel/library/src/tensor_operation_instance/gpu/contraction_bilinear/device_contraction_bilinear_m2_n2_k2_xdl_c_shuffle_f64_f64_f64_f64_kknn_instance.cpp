// SPDX-License-Identifier: MIT
// Copyright (c) 2018-2022, Advanced Micro Devices, Inc. All rights reserved.

// This (ifndef) is a hack to use customized behavior for buffer load rather than using default
// setting Don't use this hack unless absolutely necessary!
// FIXME: make the behavior of buffer load a configurable (template) parameter of each device op
#define CK_EXPERIMENTAL_USE_BUFFER_LOAD_OOB_CHECK_OFFSET_TRICK 1

#include <cstdlib>

#include "ck/ck.hpp"
#include "ck/tensor_operation/gpu/device/tensor_layout.hpp"
#include "ck/tensor_operation/gpu/device/gemm_specialization.hpp"
#include "ck/tensor_operation/gpu/device/impl/device_contraction_multiple_d_xdl_cshuffle.hpp"
#include "ck/tensor_operation/gpu/element/element_wise_operation.hpp"

#include "ck/library/tensor_operation_instance/add_device_operation_instance.hpp"

namespace ck {
namespace tensor_operation {
namespace device {
namespace instance {

using F64       = double;
using F64_Tuple = ck::Tuple<F64>;

template <ck::index_t... Is>
using S = ck::Sequence<Is...>;

using PassThrough = ck::tensor_operation::element_wise::PassThrough;
using Bilinear    = ck::tensor_operation::element_wise::Bilinear;

static constexpr auto GemmMNKPadding = ck::tensor_operation::device::GemmSpecialization::MNKPadding;

// A[m0, m1, k0, k1] * B[n0, n1, k0, k1] + D[m0, m1, n0, n1] = E[m0, m1, n0, n1]
// k/k/n/n are the fast changing dimension for A/B/D/E
using device_contraction_bilinear_m2_n2_k2_xdl_c_shuffle_f64_f64_f64_f64_kknn_instance = std::tuple<
    // clang-format off
        //#####################################| NumDimM| NumDimN| NumDimK| AData| BData| AccData| CShuffle|    DsData| EData|            A|           B|         CDE|           GEMM| NumGemmK| Block|  MPer|  NPer|  KPer| AK1| BK1| MPer| NPer| MXdl| NXdl|  ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockTransfer| ABlockLds|  BBlockTransfer| BBlockTransfer| BBlockTransfer| BlockTransfer| BBlockTransfer| BBlockTransfer| BBlockLds|    CShuffle|    CShuffle| CBlockTransferClusterLengths|  CBlockTransfer|
        //#####################################|        |        |        |  Type|  Type|    Type| DataType|      Type|  Type|  Elementwise| Elementwise| Elementwise| Specialization| Prefetch|  Size| Block| Block| Block|    |    |  XDL|  XDL|  Per|  Per|   ThreadCluster|  ThreadCluster| SrcAccessOrder|   SrcVectorDim|      SrcScalar|      DstScalar| AddExtraM|   ThreadCluster|  ThreadCluster| SrcAccessOrder|  SrcVectorDim|      SrcScalar|      DstScalar| AddExtraN| MXdlPerWave| NXdlPerWave|         _MBlock_MWaveMPerXdl| ScalarPerVector|
        //#####################################|        |        |        |      |      |        |         |          |      |    Operation|   Operation|   Operation|               |    Stage|      |      |      |      |    |    |     |     | Wave| Wave| Lengths_K0_M_K1|   ArrangeOrder|               |               |      PerVector|   PerVector_K1|          | Lengths_K0_N_K1|   ArrangeOrder|               |              |      PerVector|   PerVector_K1|          |  PerShuffle|  PerShuffle|         _NBlock_NWaveNPerXdl|   _NWaveNPerXdl|
        //#####################################|        |        |        |      |      |        |         |          |      |             |            |            |               |         |      |      |      |      |    |    |     |     |     |     |                |               |               |               |               |               |          |                |               |               |              |               |               |          |            |            |                             |                |
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,   256,   128,   128,    16,   2,   2,   16,   16,    4,    4,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1, 16, 1, 16>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,   128,   128,    64,    16,   2,   2,   16,   16,    4,    4,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1, 16, 1,  8>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,   128,    64,   128,    16,   2,   2,   16,   16,    4,    4,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1,  8, 1, 16>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,    64,    64,    64,    16,   2,   2,   16,   16,    4,    4,     S<4, 16, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 16, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1,  8, 1,  8>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,   256,   128,    64,    16,   2,   2,   16,   16,    4,    2,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1, 16, 1, 16>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,   256,    64,   128,    16,   2,   2,   16,   16,    2,    4,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 64, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1, 16, 1, 16>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,   128,   128,    32,    16,   2,   2,   16,   16,    4,    2,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1, 16, 1,  8>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,   128,    32,   128,    16,   2,   2,   16,   16,    2,    4,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 32, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1,  8, 1, 16>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,    64,    64,    32,    16,   2,   2,   16,   16,    4,    2,     S<4, 16, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 16, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1,  8, 1,  8>,               1>,
        DeviceContractionMultipleD_Xdl_CShuffle<       2,       2,       2,   F64,   F64,     F64,      F64, F64_Tuple,   F64,  PassThrough, PassThrough,    Bilinear, GemmMNKPadding,        1,    64,    32,    64,    16,   2,   2,   16,   16,    2,    4,     S<4, 16, 1>,     S<1, 0, 2>,     S<1, 0, 2>,              2,              1,              1,         1,     S<4, 16, 1>,     S<1, 0, 2>,     S<1, 0, 2>,             2,              1,              1,         1,           1,           1,              S<1,  8, 1,  8>,               1>
    // clang-format on
    >;

void add_device_contraction_bilinear_m2_n2_k2_xdl_c_shuffle_f64_f64_f64_f64_kknn_instance(
    std::vector<std::unique_ptr<DeviceContractionMultipleD<2,
                                                           2,
                                                           2,
                                                           F64,
                                                           F64,
                                                           F64_Tuple,
                                                           F64,
                                                           PassThrough,
                                                           PassThrough,
                                                           Bilinear>>>& instances)
{
    add_device_operation_instances(
        instances,
        device_contraction_bilinear_m2_n2_k2_xdl_c_shuffle_f64_f64_f64_f64_kknn_instance{});
}

} // namespace instance
} // namespace device
} // namespace tensor_operation
} // namespace ck
