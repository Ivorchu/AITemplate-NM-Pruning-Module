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
void add_device_conv2d_dl_bias_perchannel_quantization_int8_instances(
    std::vector<
        std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                      NHWGC,
                                                      GKYXC,
                                                      GK_GK_Tuple,
                                                      NHWGK,
                                                      int8_t,
                                                      int8_t,
                                                      I32_F32_Tuple,
                                                      int8_t,
                                                      PassThrough,
                                                      PassThrough,
                                                      Add_Activation_Mul2_Clamp<PassThrough>>>>&
        instances);

void add_device_conv2d_dl_bias_relu_perchannel_quantization_int8_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              NHWGC,
                                                              GKYXC,
                                                              GK_GK_Tuple,
                                                              NHWGK,
                                                              int8_t,
                                                              int8_t,
                                                              I32_F32_Tuple,
                                                              int8_t,
                                                              PassThrough,
                                                              PassThrough,
                                                              Add_Activation_Mul2_Clamp<Relu>>>>&
        instances);

void add_device_conv2d_dl_bias_tanh_perchannel_quantization_int8_instances(
    std::vector<
        std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                      NHWGC,
                                                      GKYXC,
                                                      GK_GK_Tuple,
                                                      NHWGK,
                                                      int8_t,
                                                      int8_t,
                                                      I32_F32_Tuple,
                                                      int8_t,
                                                      PassThrough,
                                                      PassThrough,
                                                      Add_Mul2_Activation_Mul_Clamp<TanH>>>>&
        instances);

void add_device_conv2d_xdl_bias_perchannel_quantization_int8_instances(
    std::vector<
        std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                      NHWGC,
                                                      GKYXC,
                                                      GK_GK_Tuple,
                                                      NHWGK,
                                                      int8_t,
                                                      int8_t,
                                                      I32_F32_Tuple,
                                                      int8_t,
                                                      PassThrough,
                                                      PassThrough,
                                                      Add_Activation_Mul2_Clamp<PassThrough>>>>&
        instances);

void add_device_conv2d_xdl_bias_relu_perchannel_quantization_int8_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              NHWGC,
                                                              GKYXC,
                                                              GK_GK_Tuple,
                                                              NHWGK,
                                                              int8_t,
                                                              int8_t,
                                                              I32_F32_Tuple,
                                                              int8_t,
                                                              PassThrough,
                                                              PassThrough,
                                                              Add_Activation_Mul2_Clamp<Relu>>>>&
        instances);

void add_device_conv2d_xdl_bias_tanh_perchannel_quantization_int8_instances(
    std::vector<
        std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                      NHWGC,
                                                      GKYXC,
                                                      GK_GK_Tuple,
                                                      NHWGK,
                                                      int8_t,
                                                      int8_t,
                                                      I32_F32_Tuple,
                                                      int8_t,
                                                      PassThrough,
                                                      PassThrough,
                                                      Add_Mul2_Activation_Mul_Clamp<TanH>>>>&
        instances);

// piecewise activation function
template <ck::index_t NumDimSpatial,
          typename InLayout,
          typename WeiLayout,
          typename DsLayout,
          typename OutLayout,
          typename InDataType,
          typename WeiDataType,
          typename DsDataType,
          typename OutDataType,
          typename Activation>
struct DeviceOperationInstanceFactory<ck::tensor_operation::device::DeviceGroupedConvFwdMultipleD<
    NumDimSpatial,
    InLayout,
    WeiLayout,
    DsLayout,
    OutLayout,
    InDataType,
    WeiDataType,
    DsDataType,
    OutDataType,
    ck::tensor_operation::element_wise::PassThrough,
    ck::tensor_operation::element_wise::PassThrough,
    Add_Activation_Mul2_Clamp<Activation>>>
{
    using DeviceOp = DeviceGroupedConvFwdMultipleD<NumDimSpatial,
                                                   InLayout,
                                                   WeiLayout,
                                                   DsLayout,
                                                   OutLayout,
                                                   InDataType,
                                                   WeiDataType,
                                                   DsDataType,
                                                   OutDataType,
                                                   ck::tensor_operation::element_wise::PassThrough,
                                                   ck::tensor_operation::element_wise::PassThrough,
                                                   Add_Activation_Mul2_Clamp<Activation>>;

    static auto GetInstances()
    {
        std::vector<std::unique_ptr<DeviceOp>> op_ptrs;

        if constexpr(NumDimSpatial == 2 && is_same_v<InLayout, NHWGC> &&
                     is_same_v<WeiLayout, GKYXC> && is_same_v<DsLayout, GK_GK_Tuple> &&
                     is_same_v<OutLayout, NHWGK>)
        {
            if constexpr(is_same_v<InDataType, int8_t> && is_same_v<WeiDataType, int8_t> &&
                         is_same_v<DsDataType, I32_F32_Tuple> && is_same_v<OutDataType, int8_t>)
            {
                if constexpr(is_same_v<Activation, PassThrough>)
                {
                    add_device_conv2d_dl_bias_perchannel_quantization_int8_instances(op_ptrs);
                    add_device_conv2d_xdl_bias_perchannel_quantization_int8_instances(op_ptrs);
                }
                else if constexpr(is_same_v<Activation, Relu>)
                {
                    add_device_conv2d_dl_bias_relu_perchannel_quantization_int8_instances(op_ptrs);
                    add_device_conv2d_xdl_bias_relu_perchannel_quantization_int8_instances(op_ptrs);
                }
            }
        }

        return op_ptrs;
    }
};

// non-piecewise activation function
template <ck::index_t NumDimSpatial,
          typename InLayout,
          typename WeiLayout,
          typename DsLayout,
          typename OutLayout,
          typename InDataType,
          typename WeiDataType,
          typename DsDataType,
          typename OutDataType,
          typename Activation>
struct DeviceOperationInstanceFactory<ck::tensor_operation::device::DeviceGroupedConvFwdMultipleD<
    NumDimSpatial,
    InLayout,
    WeiLayout,
    DsLayout,
    OutLayout,
    InDataType,
    WeiDataType,
    DsDataType,
    OutDataType,
    ck::tensor_operation::element_wise::PassThrough,
    ck::tensor_operation::element_wise::PassThrough,
    Add_Mul2_Activation_Mul_Clamp<Activation>>>
{
    using DeviceOp = DeviceGroupedConvFwdMultipleD<NumDimSpatial,
                                                   InLayout,
                                                   WeiLayout,
                                                   DsLayout,
                                                   OutLayout,
                                                   InDataType,
                                                   WeiDataType,
                                                   DsDataType,
                                                   OutDataType,
                                                   ck::tensor_operation::element_wise::PassThrough,
                                                   ck::tensor_operation::element_wise::PassThrough,
                                                   Add_Mul2_Activation_Mul_Clamp<Activation>>;

    static auto GetInstances()
    {
        std::vector<std::unique_ptr<DeviceOp>> op_ptrs;

        if constexpr(NumDimSpatial == 2 && is_same_v<InLayout, NHWGC> &&
                     is_same_v<WeiLayout, GKYXC> && is_same_v<DsLayout, GK_GK_Tuple> &&
                     is_same_v<OutLayout, NHWGK>)
        {
            if constexpr(is_same_v<InDataType, int8_t> && is_same_v<WeiDataType, int8_t> &&
                         is_same_v<DsDataType, I32_F32_Tuple> && is_same_v<OutDataType, int8_t>)
            {
                if constexpr(is_same_v<Activation, TanH>)
                {
                    add_device_conv2d_dl_bias_tanh_perchannel_quantization_int8_instances(op_ptrs);
                    add_device_conv2d_xdl_bias_tanh_perchannel_quantization_int8_instances(op_ptrs);
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
