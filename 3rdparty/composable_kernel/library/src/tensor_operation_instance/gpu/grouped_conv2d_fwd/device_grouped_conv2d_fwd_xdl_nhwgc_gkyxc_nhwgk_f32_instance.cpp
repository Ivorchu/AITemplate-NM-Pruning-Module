// SPDX-License-Identifier: MIT
// Copyright (c) 2018-2022, Advanced Micro Devices, Inc. All rights reserved.

#include "ck/library/tensor_operation_instance/add_device_operation_instance.hpp"
#include "device_grouped_conv2d_fwd_xdl_instance.hpp"

namespace ck {
namespace tensor_operation {
namespace device {
namespace instance {
// Compilation parameters for in[n, hi, wi, g, c] * wei[g, k, y, x, c] = out[n, ho, wo, g, k]
void add_device_grouped_conv2d_fwd_xdl_nhwgc_gkyxc_nhwgk_f32_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              NHWGC,
                                                              GKYXC,
                                                              Empty_Tuple,
                                                              NHWGK,
                                                              F32,
                                                              F32,
                                                              Empty_Tuple,
                                                              F32,
                                                              PassThrough,
                                                              PassThrough,
                                                              PassThrough>>>& instances)
{
    add_device_operation_instances(instances,
                                   device_grouped_conv2d_fwd_xdl_f32_instances<NHWGC,
                                                                               GKYXC,
                                                                               Empty_Tuple,
                                                                               NHWGK,
                                                                               Empty_Tuple,
                                                                               PassThrough,
                                                                               ConvFwdDefault>{});

    add_device_operation_instances(instances,
                                   device_grouped_conv2d_fwd_xdl_f32_instances<NHWGC,
                                                                               GKYXC,
                                                                               Empty_Tuple,
                                                                               NHWGK,
                                                                               Empty_Tuple,
                                                                               PassThrough,
                                                                               ConvFwd1x1P0>{});

    add_device_operation_instances(instances,
                                   device_grouped_conv2d_fwd_xdl_f32_instances<NHWGC,
                                                                               GKYXC,
                                                                               Empty_Tuple,
                                                                               NHWGK,
                                                                               Empty_Tuple,
                                                                               PassThrough,
                                                                               ConvFwd1x1S1P0>{});

    add_device_operation_instances(instances,
                                   device_grouped_conv2d_fwd_xdl_f32_instances<NHWGC,
                                                                               GKYXC,
                                                                               Empty_Tuple,
                                                                               NHWGK,
                                                                               Empty_Tuple,
                                                                               PassThrough,
                                                                               ConvFwdOddC>{});
}

} // namespace instance
} // namespace device
} // namespace tensor_operation
} // namespace ck
