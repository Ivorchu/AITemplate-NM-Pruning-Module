// SPDX-License-Identifier: MIT
// Copyright (c) 2018-2022, Advanced Micro Devices, Inc. All rights reserved.

#include "device_gemm_quantization_dl_c_shuffle_i8_i8_i8_instance.hpp"

namespace ck {
namespace tensor_operation {
namespace device {
namespace instance {

// Layout(A, B, C) = [Row, Col, Row]
void add_device_gemm_quantization_dl_c_shuffle_i8_i8_i8_mk_nk_mn_instances(
    std::vector<std::unique_ptr<DeviceGemmMultipleD<Row,
                                                    Col,
                                                    Empty_Tuple,
                                                    Row,
                                                    int8_t,
                                                    int8_t,
                                                    Empty_Tuple,
                                                    int8_t,
                                                    PassThrough,
                                                    PassThrough,
                                                    Mul_Clamp>>>& instances)
{
    add_device_operation_instances(
        instances, device_gemm_quantization_dl_c_shuffle_i8_i8_i8_mk_nk_mn_instances<Mul_Clamp>{});
}

} // namespace instance
} // namespace device
} // namespace tensor_operation
} // namespace ck
