// SPDX-License-Identifier: MIT
// Copyright (c) 2018-2022, Advanced Micro Devices, Inc. All rights reserved.

#include "ck/library/tensor_operation_instance/add_device_operation_instance.hpp"
#include "device_grouped_conv2d_fwd_dl_instance.hpp"

namespace ck {
namespace tensor_operation {
namespace device {
namespace instance {

void add_device_grouped_conv2d_fwd_dl_gnhwc_gkyxc_gnhwk_f16_instances(
    std::vector<std::unique_ptr<DeviceGroupedConvFwdMultipleD<2,
                                                              GNHWC,
                                                              GKYXC,
                                                              Empty_Tuple,
                                                              GNHWK,
                                                              F16,
                                                              F16,
                                                              Empty_Tuple,
                                                              F16,
                                                              PassThrough,
                                                              PassThrough,
                                                              PassThrough>>>& instances)
{
    add_device_operation_instances(instances,
                                   device_grouped_conv2d_fwd_dl_f16_instances<GNHWC,
                                                                              GKYXC,
                                                                              Empty_Tuple,
                                                                              GNHWK,
                                                                              Empty_Tuple,
                                                                              PassThrough,
                                                                              ConvFwdDefault>{});

    add_device_operation_instances(instances,
                                   device_grouped_conv2d_fwd_dl_f16_instances<GNHWC,
                                                                              GKYXC,
                                                                              Empty_Tuple,
                                                                              GNHWK,
                                                                              Empty_Tuple,
                                                                              PassThrough,
                                                                              ConvFwd1x1P0>{});

    add_device_operation_instances(instances,
                                   device_grouped_conv2d_fwd_dl_f16_instances<GNHWC,
                                                                              GKYXC,
                                                                              Empty_Tuple,
                                                                              GNHWK,
                                                                              Empty_Tuple,
                                                                              PassThrough,
                                                                              ConvFwd1x1S1P0>{});
}

} // namespace instance
} // namespace device
} // namespace tensor_operation
} // namespace ck
