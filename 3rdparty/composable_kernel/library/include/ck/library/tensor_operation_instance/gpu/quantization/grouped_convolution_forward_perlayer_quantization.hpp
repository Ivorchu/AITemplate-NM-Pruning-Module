// SPDX-License-Identifier: MIT
// Copyright (c) 2018-2022, Advanced Micro Devices, Inc. All rights reserved.

#pragma once

#include <cstdlib>

#include "ck/ck.hpp"
#include "ck/tensor_operation/gpu/device/tensor_layout.hpp"
#include "ck/tensor_operation/gpu/device/device_grouped_conv_fwd_multiple_d.hpp"
#include "ck/tensor_operation/gpu/element/element_wise_operation.hpp"

#include "ck/library/tensor_operation_instance/device_operation_instance_factory.hpp"

namespace ck {
namespace tensor_operation {
namespace device {
namespace instance {

// grouped conv2d forward, NHWGC/GKYXC/NHWGK
void add_device_conv2d_dl_perlayer_quantization_int8_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              NHWGC,
                                                              GKYXC,
                                                              Empty_Tuple,
                                                              NHWGK,
                                                              int8_t,
                                                              int8_t,
                                                              Empty_Tuple,
                                                              int8_t,
                                                              PassThrough,
                                                              PassThrough,
                                                              Activation_Mul_Clamp<PassThrough>>>>&
        instances);

void add_device_conv2d_dl_relu_perlayer_quantization_int8_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              NHWGC,
                                                              GKYXC,
                                                              Empty_Tuple,
                                                              NHWGK,
                                                              int8_t,
                                                              int8_t,
                                                              Empty_Tuple,
                                                              int8_t,
                                                              PassThrough,
                                                              PassThrough,
                                                              Activation_Mul_Clamp<Relu>>>>&
        instances);

void add_device_conv2d_xdl_perlayer_quantization_int8_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              NHWGC,
                                                              GKYXC,
                                                              Empty_Tuple,
                                                              NHWGK,
                                                              int8_t,
                                                              int8_t,
                                                              Empty_Tuple,
                                                              int8_t,
                                                              PassThrough,
                                                              PassThrough,
                                                              Activation_Mul_Clamp<PassThrough>>>>&
        instances);

void add_device_conv2d_xdl_relu_perlayer_quantization_int8_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              NHWGC,
                                                              GKYXC,
                                                              Empty_Tuple,
                                                              NHWGK,
                                                              int8_t,
                                                              int8_t,
                                                              Empty_Tuple,
                                                              int8_t,
                                                              PassThrough,
                                                              PassThrough,
                                                              Activation_Mul_Clamp<Relu>>>>&
        instances);

template <ck::index_t NumDimSpatial,
          typename InLayout,
          typename WeiLayout,
          typename OutLayout,
          typename InDataType,
          typename WeiDataType,
          typename OutDataType,
          typename Activation>
struct DeviceOperationInstanceFactory<ck::tensor_operation::device::DeviceGroupedConvFwdMultipleD<
    NumDimSpatial,
    InLayout,
    WeiLayout,
    Empty_Tuple,
    OutLayout,
    InDataType,
    WeiDataType,
    Empty_Tuple,
    OutDataType,
    ck::tensor_operation::element_wise::PassThrough,
    ck::tensor_operation::element_wise::PassThrough,
    Activation_Mul_Clamp<Activation>>>
{
    using DeviceOp = DeviceGroupedConvFwdMultipleD<NumDimSpatial,
                                                   InLayout,
                                                   WeiLayout,
                                                   Empty_Tuple,
                                                   OutLayout,
                                                   InDataType,
                                                   WeiDataType,
                                                   Empty_Tuple,
                                                   OutDataType,
                                                   ck::tensor_operation::element_wise::PassThrough,
                                                   ck::tensor_operation::element_wise::PassThrough,
                                                   Activation_Mul_Clamp<Activation>>;

    static auto GetInstances()
    {
        std::vector<std::unique_ptr<DeviceOp>> op_ptrs;

        if constexpr(NumDimSpatial == 2 && is_same_v<InLayout, NHWGC> &&
                     is_same_v<WeiLayout, GKYXC> && is_same_v<OutLayout, NHWGK>)
        {
            if constexpr(is_same_v<InDataType, int8_t> && is_same_v<WeiDataType, int8_t> &&
                         is_same_v<OutDataType, int8_t>)
            {
                if constexpr(is_same_v<Activation, PassThrough>)
                {
                    add_device_conv2d_dl_perlayer_quantization_int8_instances(op_ptrs);
                    add_device_conv2d_xdl_perlayer_quantization_int8_instances(op_ptrs);
                }
                else if constexpr(is_same_v<Activation, Relu>)
                {
                    add_device_conv2d_dl_relu_perlayer_quantization_int8_instances(op_ptrs);
                    add_device_conv2d_xdl_relu_perlayer_quantization_int8_instances(op_ptrs);
                }
            }
        }

        return op_ptrs;
    }
};

} // namespace instance
} // namespace device
} // namespace tensor_operation
} // namespace ck
