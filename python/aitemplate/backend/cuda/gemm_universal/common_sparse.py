#  Copyright (c) Meta Platforms, Inc. and affiliates.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""
Common codegen functions for gemm.
"""

import os
import random
import re
from collections import OrderedDict
from hashlib import sha1
from typing import Any, Dict, List, Tuple

import jinja2

from aitemplate.backend.backend_spec import CUDASpec

from aitemplate.backend.common import gemm_sparse_common, tensor_accessor_codegen
from aitemplate.backend.target import Target

from aitemplate.compiler.base import IntImm, ExecItem
from aitemplate.utils import alignment


# pylint: disable=C0301,C0415,R1705


INPUT_ADDR_CALCULATOR = jinja2.Template(
    """
  int64_t input_a_batch_stride = {{input_a_batch_stride_dim}};
  int64_t input_a_stride = {{input_a_stride_dim}};
  int64_t input_a_offset = {{input_a_offset_val}}; // default to 0
  int64_t input_b_batch_stride = {{input_b_batch_stride_dim}};
  int64_t input_b_stride = {{input_b_stride_dim}};
  int64_t input_b_offset = {{input_b_offset_val}}; // default to 0
    """
)


# These should be only used for 2D gemm
# For templates for bmm, see bmm_common
OUTPUT_ADDR_CALCULATOR = jinja2.Template(
    """
  {% if not output_accessor.is_from_strided_tensor %}
  int64_t output_batch_stride = {{output_batch_stride_dim}};
  int64_t output_stride = {{output_stride_dim}};
  int64_t output_offset = 0;
  {% else %}
  int64_t output_batch_stride = {{output_accessor.stride(output_accessor.rank - 2)}};
  int64_t output_stride = {{output_accessor.stride(output_accessor.rank - 1)}};
  int64_t output_offset = {{output_accessor.offset}};
  {% endif %}
    """
)

DEFAULT_OUTPUT_ADDR_CALCULATOR = jinja2.Template(
    """
  int64_t output_batch_stride = {{output_batch_stride_dim}};
  int64_t output_stride = {{output_stride_dim}};
  int64_t output_offset = 0;
    """
)

DIM_DEFS_TEMPLATE = jinja2.Template(
    """
{% for dim, value in dims.items() %}
{{indent}}int64_t {{dim}} = {{value}};
{% endfor %}
"""
)


INPUT_OUTPUT_CHECKS_TEMPLATE = jinja2.Template(
    """
  int64_t a_size = 1;
{% for idx in range(input_ndims) %}
    a_size *= *a_dim{{idx}};
{% endfor %}
  if (a_size != 0 && !a_ptr) {
    throw std::runtime_error("input a is null!");
  }

  int64_t b_size = 1;
{% for idx in range(weight_ndims) %}
    b_size *= *b_dim{{idx}};
{% endfor %}
  if (b_size != 0 && !b_ptr) {
    throw std::runtime_error("input b is null!");
  }

  int64_t m_size = 1;
{% for idx in range(meta_ndims) %}
    m_size *= *m_dim{{idx}};
{% endfor %}
  if (m_size != 0 && !m_ptr) {
    throw std::runtime_error("input m is null!");
  }

  int64_t c_size = 1;
{% for idx in range(output_ndims) %}
    c_size *= *c_dim{{idx}};
{% endfor %}
  if (c_size != 0) {
    if (!c_ptr) {
      throw std::runtime_error("input c is null!");
    }
  } else {
    // output is empty and safe to return
    return;
  }

  // One of the input tensor are empty
  if (a_size == 0 || b_size == 0) {
    return;
  }
"""
)

INSTANCE_TEMPLATE = jinja2.Template(
    """
{{config}}
using {{name}} = {{config_name}};
"""
)

INSTANCE_TEMPLATE_CUTLASS_3X = jinja2.Template(
    """
{{config}}
using {{name}} = cutlass::gemm::device::GemmUniversalAdapter<{{config_name}}>;
"""
)

INSTANCE_TEMPLATE_SPARSE = jinja2.Template("""
{{config}}
using {{name}} = cutlass::gemm::device::SparseGemm<{{config_name}}>;
""")


SRC_TEMPLATE = jinja2.Template(
    """
#include <iostream>
#include <memory>
#include <random>
#include <vector>

#include "cutlass/cutlass.h"
#include "cutlass/gemm/device/gemm_universal.h"
#include "cutlass/gemm/device/gemm_sparse.h"
#include "cutlass/gemm/kernel/gemm_grouped.h"
#include "cutlass/gemm/kernel/default_gemm_grouped.h"
#include "cutlass/gemm/device/gemm_grouped.h"
#include "cutlass/util/host_tensor.h"
#include "cutlass/util/reference/host/tensor_fill.h"
#include "cutlass/util/reference/device/tensor_fill.h"
#include "cutlass/util/device_memory.h"

#include "cutlass/util/reference/host/gemm.h"
#include "cutlass/util/host_reorder.h"
#include "cutlass/util/host_uncompress.h"
#include "cutlass/util/reference/host/tensor_compare.h"
#include "cutlass/util/reference/host/tensor_copy.h"
#include "cutlass/util/tensor_view_io.h"

#include "cutlass/gemm/gemm.h"
#include "cutlass/numeric_types.h"
#include "cutlass/gemm/kernel/gemm_universal.hpp"
#include "cutlass/gemm/collective/collective_builder.hpp"
#include "cutlass/gemm/device/gemm_universal_adapter.h"
#include "cutlass/epilogue/collective/collective_builder.hpp"

#include "cutlass/tensor_ref.h"
#include "cutlass/gemm/threadblock/threadblock_swizzle.h"
#include "cutlass/epilogue/thread/linear_combination.h"
#include "cutlass/arch/mma.h"

using bfloat16 = nv_bfloat16;

{{extra_code}}

#define CUTLASS_CHECK(status)                                                         \\
  {                                                                                   \\
    cutlass::Status error = status;                                                   \\
    if (error != cutlass::Status::kSuccess) {                                         \\
      auto msg = std::string("[") + __FILE__ + "] Got cutlass error: " +              \\
          cutlassGetStatusString(error) + " at: " + std::to_string(__LINE__);         \\
      std::cerr << msg << std::endl;                                                  \\
      throw std::runtime_error(msg);                                                  \\
    }                                                                                 \\
  }

{{instances}}

{% if is_profiler %}
template <typename GemmInstance>
void {{function_name}} (
    GemmInstance& gemm_op,
{% else %}
void {{function_name}} (
{% endif %}
    void* a_ptr,
    void* b_ptr,
    void* m_ptr,
    void* c_ptr,
    uint8_t* workspace,
{% if support_split_k %}
    int split_k,
{% endif %}
{% for idx in range(weight_ndims) %}
    int64_t* a_dim{{idx}},
{% endfor %}
{% for idx in range(input_ndims) %}
    int64_t* b_dim{{idx}},
{% endfor %}
{% for idx in range(meta_ndims) %}
    int64_t* m_dim{{idx}},
{% endfor %}
{% for idx in range(output_ndims) %}
    int64_t* c_dim{{idx}},
{% endfor %}
    cudaStream_t stream
  ) {
  {{shape_eval}}
    //using ElementE = typename GemmInstance::ElementE;

  {{input_addr_calculator}}
  {{output_addr_calculator}}

  {{input_output_checks}}

  
#if 0
std::vector<cutlass::half_t> host_A(a_size);

// Copy from device (A_ptr) to host
cudaMemcpy(host_A.data(), a_ptr, a_size * sizeof(cutlass::half_t), cudaMemcpyDeviceToHost);

std::cout << std::endl << "Contents of A:" << std::endl;
for (int i = 0; i < std::min<int64_t>(30, a_size); i++) {
    float val = __half2float(static_cast<__half>(host_A[i]));
    std::cout << val << " ";
    if ((i + 1) % (*a_dim1) == 0) std::cout << std::endl;
}
#endif

#if 0
std::vector<cutlass::half_t> host_B(b_size);

// Copy from device (B_ptr) to host
cudaMemcpy(host_B.data(), b_ptr, b_size * sizeof(cutlass::half_t), cudaMemcpyDeviceToHost);

std::cout << std::endl << "Contents of B:" << std::endl;
for (int i = 0; i < std::min<int64_t>(30, b_size); i++) {
    float val = __half2float(static_cast<__half>(host_B[i]));
    std::cout << val << " ";
    if ((i + 1) % (*b_dim1) == 0) std::cout << std::endl;
}
#endif

#if 0
std::vector<uint32_t> host_M(m_size);

// Copy from device (m_ptr) to host
cudaMemcpy(host_M.data(), m_ptr, m_size * sizeof(uint32_t), cudaMemcpyDeviceToHost);

std::cout << std::endl << "Contents of M:" << std::endl;
for (int i = 0; i < 30; i++) {
    std::cout << host_M[i] << " ";
    if ((i + 1) % (*m_dim1) == 0) std::cout << std::endl;
}
#endif

#if 0
std::vector<cutlass::half_t> host_C(c_size);

// Copy from device (c_ptr) to host
cudaMemcpy(host_C.data(), c_ptr, c_size * sizeof(cutlass::half_t), cudaMemcpyDeviceToHost);

std::cout << std::endl << "Contents of C (GEMM output before execution):" << std::endl;
for (int i = 0; i < std::min<int64_t>(30, c_size); i++) {
    float val = __half2float(static_cast<__half>(host_C[i]));
    std::cout << val << " ";
    if ((i + 1) % (*c_dim1) == 0) std::cout << std::endl;
}
#endif

  {{exec_paths}}

#if 0
std::vector<cutlass::half_t> host_C_after(c_size);

// Copy from device (c_ptr) to host
cudaMemcpy(host_C_after.data(), c_ptr, c_size * sizeof(cutlass::half_t), cudaMemcpyDeviceToHost);

std::cout << std::endl << "Contents of C (GEMM output after execution):" << std::endl;
for (int i = 0; i < std::min<int64_t>(30, c_size); i++) {
    float val = __half2float(static_cast<__half>(host_C_after[i]));
    std::cout << val << " ";
    if ((i + 1) % (*c_dim1) == 0) std::cout << std::endl;
}
#endif

  
#if 0
  {% for idx in range(weight_ndims) %}
      std::cout << "weight_ndims{{idx}}: " << *a_dim{{idx}} << std::endl;
  {% endfor %}
  {% for idx in range(input_ndims) %}
      std::cout << "input_ndims{{idx}}: " << *b_dim{{idx}} << std::endl;
  {% endfor %}
  {% for idx in range(meta_ndims) %}
      std::cout << "meta_ndims{{idx}}: " << *m_dim{{idx}} << std::endl;
  {% endfor %}
  {% for idx in range(output_ndims) %}
      std::cout << "output_ndims{{idx}}: " << *c_dim{{idx}} << std::endl;
  {% endfor %}
#endif
  /*
  throw std::runtime_error(
      "Unsupported workload for this {{function_name}} specialization."
  );
  */
}
""",
    trim_blocks=True,
    lstrip_blocks=True,
)


EXEC_TEMPLATE = jinja2.Template(
    """
//  TODO: cast to right dtype
{{indent}}using ElementComputeEpilogue = typename {{instance}}::ElementAccumulator;
{{indent}}using ElementE = typename {{instance}}::ElementE;

{{indent}}using coord_t = cutlass::gemm::GemmCoord::Index;
{{indent}}typename {{instance}}::Arguments arguments;

{{indent}}if constexpr (cutlass::gemm::detail::IsCutlass3GemmKernel<typename {{instance}}::GemmKernel>::value) {
{{indent}}arguments = {
{{problem_args_cutlass_3x}}
{{indent}}};
{{indent}}} else {
{{indent}}arguments = {
{{problem_args}}
{{indent}}};
{{indent}}}

{% if is_profiler %}
{{indent}}size_t workspace_size = gemm_op.get_workspace_size(arguments);
{{indent}}cutlass::device_memory::allocation<uint8_t> local_workspace(workspace_size);
{{indent}}workspace = local_workspace.get();
{{indent}}GLOBAL_WORKSPACE_SIZE = workspace_size;
{% else %}
{{indent}}{{instance}} gemm_op;
{% endif %}
{{indent}}auto status = gemm_op.can_implement(arguments);
{{indent}}CUTLASS_CHECK(status);
{{indent}}status = gemm_op.initialize(arguments, workspace, stream);
{{indent}}CUTLASS_CHECK(status);
{{indent}}status = gemm_op(stream);
{{indent}}CUTLASS_CHECK(status);
{{indent}}return;
"""
)


FUNC_DECL_TEMPLATE = jinja2.Template(
    """
void {{func_name}}(
  void*,        // ptr_A
  void*,        // ptr_B (values)
{% if has_metadata %}
  void*,        // ptr_B_meta
{% endif %}
  void*,        // ptr_C (output)
  uint8_t*,     // workspace
{% if support_split_k %}
  int,          // split_k
{% endif %}
{% for idx in range(input_ndims) %}
  int64_t*,     // a_dim{{idx}}
{% endfor %}
{% for idx in range(weight_ndims) %}
  int64_t*,     // b_dim{{idx}}
{% endfor %}
{% if has_metadata %}
{% for idx in range(meta_ndims) %}
  int64_t*,     // bm_dim{{idx}}
{% endfor %}
{% endif %}
{% for idx in range(input_ndims) %}
  int64_t*,     // c_dim{{idx}}
{% endfor %}
  cudaStream_t  // stream
);
"""
)


FUNC_CALL_TEMPLATE = jinja2.Template(
    """
{{indent}}{
{{indent}}{{local_dim_defs}}
{{indent}}{{func_name}}(
{% if is_profiler %}
{{indent}}    gemm_op,
{% endif %}
{{indent}}    {{a_ptr}},                // A values
{{indent}}    {{b_ptr}},                // B values
{{indent}}    {{metadata_ptr}},         // B metadata
{% if has_bias %}
{{indent}}    {{bias_ptr}},             // bias (if any)
{% endif %}
{{indent}}    {{c_ptr}},                // output
{{indent}}    global_workspace_,
{{indent}}    {{split_k}},
{% for dim in adims %}
{{indent}}    {{dim}},
{% endfor %}
{% for dim in bdims %}
{{indent}}    {{dim}},
{% endfor %}
{% for dim in mdims %}
{{indent}}    {{dim}},
{% endfor %}
{% for dim in cdims %}
{{indent}}    {{dim}},
{% endfor %}
{{indent}}    stream
{{indent}});
{{indent}}}
"""
)


BENCHMARK_INSTANCE_TEMPLATE = jinja2.Template(
    """
{{indent}}{
{{indent}}
{{indent}}{{instance_name}} {{gemm_op}};
{{indent}}const char *gemm_op_name = "{{gemm_op_name}}";
{{indent}}int ret = 0;
{{indent}}try {
{{indent}}ret = {{func_name}}(
{{indent}}    {{gemm_op}},
{{indent}}    gemm_op_name,
{{indent}}    memory_pool.get(),
{{indent}}    global_workspace_,
{% if support_split_k %}
{{indent}}    {{split_k}},
{% endif %}
{% for dim in adims %}
{{indent}}    {{dim}},
{% endfor %}
{% for dim in bdims %}
{{indent}}    {{dim}},
{% endfor %}
{% for dim in mdims %}
{{indent}}    {{dim}},
{% endfor %}
{% for dim in cdims %}
{{indent}}    {{dim}},
{% endfor %}
{{indent}}    stream
{{indent}});
{{indent}}} catch (...) {}
{{indent}}if (ret != 0)
{{indent}}  return ret;
{{indent}}
{{indent}}}
"""
)


TENSOR_DECL_TEMPLATE = jinja2.Template(
    """
  int64_t a_ptr_sz = a_dim0 * a_dim1;
  int64_t b_ptr_sz = b_dim0 * b_dim1;
  int64_t m_ptr_sz = m_dim0 * m_dim1;
  int64_t c_ptr_sz = c_dim0 * c_dim1;

  // The value 1 is used to force ptr_max_sz to be non-zero
  int64_t ptr_max_sz = std::max<int64_t>({1, a_ptr_sz, b_ptr_sz, m_ptr_sz, c_ptr_sz});

  size_t one_copy_sz = a_ptr_sz + b_ptr_sz + m_ptr_sz + c_ptr_sz;
{% if has_bias %}
  one_copy_sz += c_dim1;
{%endif%}
  int64_t mem_pool_sz = memory_pool->ComputeMemPoolSize(one_copy_sz, ptr_max_sz, device_properties.l2CacheSize);

  memory_pool->AllocateTensor(a_ptr_sz, mem_pool_sz);  // a_ptr: index 0
  memory_pool->AllocateTensor(b_ptr_sz, mem_pool_sz);  // b_ptr: index 1
  memory_pool->AllocateTensor(m_ptr_sz, mem_pool_sz);  // m_ptr: index 0
  memory_pool->AllocateTensor(c_ptr_sz, mem_pool_sz, /*is_output*/true);  // c_ptr: index 2

{% if has_bias %}
  memory_pool->AllocateTensor(c_dim1, mem_pool_sz);  // bias_ptr: index 3
{% endif %}
"""
)


# TODO Merge all alignment into single profiler
PROFILER_TEMPLATE = jinja2.Template(
    """
size_t GLOBAL_WORKSPACE_SIZE = 0;

#include <sstream>

{{op_func}}

template <typename DType>
struct ProfilerMemoryPool;

template <typename GemmInstance>
int benchmark_{{function_name}} (
{% if is_group_gemm %}
    GemmInstance &gemm_op,
    const char *gemm_op_name,
    int sharedMemPerMultiprocessor,
    int multiProcessorCount,
    uint8_t* global_workspace_,
    int problem_count,
    cutlass::gemm::GemmCoord* problem_sizes_device,
    void **ptr_A,
    void **ptr_B,
    void **ptr_M,
{% if has_bias %}
    void **ptr_bias,
{% endif %}
    void **ptr_C,
    int64_t* lda,
    int64_t* ldb,
    int64_t* ldm,
    int64_t* ldc,
{% if has_bias %}
    int64_t* ldd,
{% endif %}
    int occupancy,
    cudaStream_t stream

{% else %}

    GemmInstance &gemm_op,
    const char *gemm_op_name,
    ProfilerMemoryPool<{{elem_type}}>* memory_pool,
    uint8_t* global_workspace_,
{% if support_split_k %}
    int split_k,
{% endif %}
/**
// raw pointers
void** ptr_A,                // A values
void** ptr_B,                // B values
void** ptr_M,                // B metadata
{% if has_bias %}void** ptr_bias,{% endif %}
void** ptr_C,                // output
**/
{% for idx in range(input_ndims) %}
    int64_t* a_dim{{idx}},
{% endfor %}
{% for idx in range(weight_ndims) %}
    int64_t* b_dim{{idx}},
{% endfor %}
{% for idx in range(meta_ndims) %}
    int64_t* m_dim{{idx}},
{% endfor %}
{% for idx in range(output_ndims) %}
    int64_t* c_dim{{idx}},
{% endfor %}
    cudaStream_t stream
{% endif %}
  ) {
  // warmup
  for (int i = 0; i < 5; ++i) {
    {{func_call}}
  }
  cudaEvent_t events[2];
  for (auto & event : events) {
    cudaEventCreate(&event);
  }
  cudaEventRecord(events[0], stream);
  for (int i = 0; i < 10; ++i) {
    {{func_call}}
  }
  cudaEventRecord(events[1], stream);
  cudaEventSynchronize(events[1]);
  float runtime_ms = 0;
  cudaEventElapsedTime(&runtime_ms, events[0], events[1]);
  for (auto event : events) {
    (void)cudaEventDestroy(event);
  }
  // TODO: output workspace
  if (runtime_ms < 0.00001) {
      throw std::runtime_error(
      "OOB in cutlass."
    );
  }
  std::cout << "OP:" << gemm_op_name << ",";
  std::cout << "TIME:" << runtime_ms << ",";
  std::cout << "WS:" << GLOBAL_WORKSPACE_SIZE << std::endl;
  return 0;
}

template <typename DType>
struct ProfilerMemoryPool {
  ProfilerMemoryPool() : shared_input_tensor(false) {
    std::random_device rd;
    gen = std::mt19937(rd());
    uniform_dist = std::uniform_int_distribution<int64_t>(1, 48964896);
    offsets.reserve(512);
    strides.reserve(512);
    copies.reserve(512);
    ptrs.reserve(512);
    blobs.reserve(512);
  }
  ~ProfilerMemoryPool() {}

  int64_t ComputeMemPoolSize(size_t one_copy_sz, size_t ptr_max_sz, size_t l2_cache_bytes) {
    int times_covers_l2_cache = (int)std::ceil(l2_cache_bytes / sizeof(DType) / ptr_max_sz);
    int64_t mem_pool_sz = std::max(2, std::min(512, times_covers_l2_cache));
    size_t free_global_mem = 0;
    size_t total_global_mem = 0;
    cudaError_t cuda_error = cudaMemGetInfo(&free_global_mem, &total_global_mem);
    if (cuda_error != cudaSuccess) {
      auto error_msg = std::string("Failed to invoke cudaMemGetInfo: ") +
          cudaGetErrorName(cuda_error) + ", at " + __FILE__;
      throw std::runtime_error(error_msg);
    }
    size_t single_copy_nbytes = one_copy_sz * sizeof(DType);
    while (mem_pool_sz > 0) {
      size_t nbytes = single_copy_nbytes * mem_pool_sz;
      if (nbytes < free_global_mem) {
        break;
      }
      mem_pool_sz--;
    }

    if (mem_pool_sz <= 1) {
      size_t minimal_required_nbytes = ptr_max_sz * sizeof(DType);
      if (minimal_required_nbytes > free_global_mem) {
        // We absolutely run out of memory
        auto error_msg = std::string("no enough GPU memory: requested ") +
            std::to_string(minimal_required_nbytes) + ", available: " +
            std::to_string(free_global_mem) + ", ptr_max_sz: " +
            std::to_string(ptr_max_sz) + ", at " + __FILE__;
        throw std::runtime_error(error_msg);
      } else {
        // Let's try to allocate a single blob that is large enough to hold
        // all input tensors. Note that this is still an approximation, because
        // we may still hit cudaErrorMemoryAllocation error while allocating
        // memory for the output. We will rely on cudaMalloc to throw out
        // an exception in such a case.
        shared_input_tensor = true;
        AllocateGaussianTensor(ptr_max_sz);
      }
      return 1;
    }
    return mem_pool_sz;
  }

  DType* AllocateGaussianTensor(int64_t size) {
    size_t length = size * sizeof(DType);
    blobs.emplace_back(length);
    DType* ptr = reinterpret_cast<DType*>(blobs.back().get());

    uint64_t seed = uniform_dist(gen);
    double mean = 0.f;
    double std = 1.f;

    cutlass::reference::device::BlockFillRandomGaussian(ptr, size, seed, mean,
                                                        std);

    return ptr;
  }

  int AllocateTensor(int64_t size, int64_t copy, bool is_output = false) {
    offsets.push_back(0);
    strides.push_back(size);
    copies.push_back(copy);
    DType *ptr;
    if (!is_output && shared_input_tensor) {
      ptr = reinterpret_cast<DType*>(blobs.back().get());
    } else {
      ptr = AllocateGaussianTensor(size * copy);
    }
    ptrs.push_back(reinterpret_cast<void*>(ptr));
    return ptrs.size() - 1;
  }

  DType* RequestTensorByIdx(int idx) {
    auto copy = copies.at(idx);
    auto offset = offsets.at(idx);
    auto stride = strides.at(idx);
    DType* ptr = reinterpret_cast<DType*>(ptrs.at(idx));
    ptr += offset;
    offset += stride;
    if (offset == copy * stride) {
        offset = 0;
    }
    offsets[idx] = offset;
    return ptr;
  }

  std::vector<int64_t> offsets;
  std::vector<int64_t> strides;
  std::vector<int64_t> copies;
  std::vector<void*> ptrs;
  std::vector<cutlass::DeviceAllocation<uint8_t> > blobs;
  std::mt19937 gen;
  std::uniform_int_distribution<int64_t> uniform_dist;
  // make a shared blob to hold all inputs in cases we do not have
  // enough GPU memory
  bool shared_input_tensor;
};


int main(int argc, char** argv) {
  int device_idx;
  cudaDeviceProp device_properties;
  cudaError_t result = cudaGetDevice(&device_idx);
  auto memory_pool = std::make_unique<ProfilerMemoryPool<{{elem_type}}>>();
  if (result != cudaSuccess) {
    std::ostringstream errorStream;
    errorStream << "cudaGetDevice() call failed! "
                << "Error code: " << cudaGetErrorName(result)
                << " Error message: " << cudaGetErrorString(result);
    throw std::runtime_error(errorStream.str());
  }

  result = cudaGetDeviceProperties(&device_properties, device_idx);

  if (result != cudaSuccess) {
    std::ostringstream errorStream;
    errorStream << "cudaGetDeviceProperties() call failed! "
                << "Error code: " << cudaGetErrorName(result)
                << " Error message: " << cudaGetErrorString(result);
    throw std::runtime_error(errorStream.str());
  }

  {{args_parse}}

  uint8_t* global_workspace_ = nullptr;
  cudaStream_t stream = nullptr;

  {{tensor_decl}}

  {{benchmark_instances}}
  return 0;
}
"""
)


KERNEL_KEY_TEMPLATE = jinja2.Template(
    """
cutlass{{prefix}}_{{opcode_class_name}}_{{extended_name}}_{{threadblock}}_{{layout}}_align_{{align_ab}}_{{align_c}}
"""
)


def has_d(func_attrs):
    if "has_d" in func_attrs:
        return func_attrs["has_d"]
    else:
        return False


def has_d1(func_attrs):
    return func_attrs.get("num_sources", 0) >= 2


def get_gemm_instance_template_params(
    op_def: str,
    kernel_config: Tuple[str, int, int] = ("cutlass::gemm::device::Gemm", 21, 3),
) -> List[str]:
    """
    For a given op_def string generated by cutlass's gemm emiter, parse and
    return the gemm instance's template parameters.
    kernel_config is a tuple used for finding kernel params. The first element
    of kernel_config is the kernel kind, the second is the expected number
    of params, and the third is the index offset of alignment values in the
    full op_def string.
    """
    kernel_kind, expected_num_params, _ = kernel_config
    params = re.findall(rf"{kernel_kind}<([\s\S]+)>;", op_def)
    assert len(params) == 1
    param = params[0]
    gemm_universal_params = param.strip().split("\n")
    gemm_universal_params = [param.strip(",") for param in gemm_universal_params]
    assert len(gemm_universal_params) == expected_num_params, (
        f"expected len(gemm_universal_params) to be {expected_num_params}, but got "
        f"{len(gemm_universal_params)}, {gemm_universal_params=}"
    )
    return gemm_universal_params


def get_tensor_accessor_alignments(func_attrs):
    """Infer the A, B, and epilogue alignments from the respective TAs."""
    input_accessors = func_attrs["input_accessors"]
    a_alignment = tensor_accessor_codegen.find_max_alignment_for_accessor(
        input_accessors[0]
    )
    b_alignment = tensor_accessor_codegen.find_max_alignment_for_accessor(
        input_accessors[1]
    )
    output_accessor = func_attrs["output_accessors"][0]
    epilogue_alignment = tensor_accessor_codegen.find_max_alignment_for_accessor(
        output_accessor
    )

    # if the last dim is dynamic, force align=1
    if not isinstance(output_accessor.original_shapes[-1], IntImm):
        epilogue_alignment = 1

    return a_alignment, b_alignment, epilogue_alignment


def update_alignments_in_gemm_instance(
    op_def: str,
    func_attrs: Dict[str, Any],
    for_profiler: bool,
    kernel_config: Tuple[str, int, int] = ("cutlass::gemm::device::SparseGemm", 21, 3),
) -> str:
    """
    update kAlignmentA, kAlignmentB, and epilogue_alignment in op_def,
    which is a gemm instance emitted by the gemm instance emitter of cutlass.
    kernel_config is a tuple used for finding kernel params. The first element
    of kernel_config is the kernel kind, the second is the expected number
    of params, and the third is the index offset of alignment values in the
    full op_def string.
    """
    if for_profiler:
        return op_def

    a_alignment, b_alignment, epilogue_alignment = get_tensor_accessor_alignments(
        func_attrs
    )

    gemm_params = get_gemm_instance_template_params(op_def, kernel_config)
    epilogue_align_idx = 11
    a_align_idx = 17
    b_align_idx = 18
    a_curr_align = gemm_params[a_align_idx].strip()
    b_curr_align = gemm_params[b_align_idx].strip()
    epilogue_curr_align = gemm_params[epilogue_align_idx].strip()
    a_alignment = min(a_alignment, int(a_curr_align))
    b_alignment = min(b_alignment, int(b_curr_align))
    epilogue_alignment = min(epilogue_alignment, int(epilogue_curr_align))
    instance_lines = op_def.split("\n")
    # a_align_idx + idx_offset in the full instance string
    idx_offset = kernel_config[2]

    def _replace_align(align_idx, curr_align, alignment):
        curr_align_line = instance_lines[align_idx + idx_offset]
        assert curr_align == curr_align_line.strip(
            " ,"
        ), f"expected {curr_align=} equal to {curr_align_line=}"
        instance_lines[align_idx + idx_offset] = curr_align_line.replace(
            curr_align, str(alignment)
        )

    _replace_align(a_align_idx, a_curr_align, a_alignment)
    _replace_align(b_align_idx, b_curr_align, b_alignment)
    _replace_align(epilogue_align_idx, epilogue_curr_align, epilogue_alignment)
    return "\n".join(instance_lines)


def universal_gemm_instance(
    op_def: str,
    func_attrs: Dict[str, Any],
    for_profiler: bool,
    cutlass_3x: bool = False,
) -> str:
    if cutlass_3x:
        # We don't need to make any adjustments to the emitted
        # CUTLASS 3.x op definitions. In particular, the alignments
        # should not be updated, as the op instances incompatible
        # with the TA-specified alignments have been removed from
        # consideration by the filter_cutlass_3x_ops function.
        return op_def

    op_def = update_alignments_in_gemm_instance(op_def, func_attrs, for_profiler)
    tmp = op_def.replace(
        "cutlass::gemm::device::Gemm", "cutlass::gemm::device::GemmUniversal"
    )
    tmp = tmp.replace("false,", "")
    return tmp


def sparse_gemm_instance(
    op_def: str,
    func_attrs: Dict[str, Any],
    for_profiler: bool,
    cutlass_3x: bool = False,
) -> str:
    if cutlass_3x:
        return op_def

    op_def = update_alignments_in_gemm_instance(op_def, func_attrs, for_profiler)
    tmp = op_def.replace(
        "cutlass::gemm::device::Gemm", "cutlass::gemm::device::SparseGemm"
    )
    # tmp = tmp.replace("false,", "")
    # tmp = tmp.replace("cutlass::arch::OpMultiplyAdd", "")
    return tmp


def kernel_name(op):
    """Returns kernel_name of a given cutlass op_instance."""
    from cutlass_lib import library

    threadblock = op.tile_description.procedural_name()
    extended_name = op.extended_name()
    opcode_class_name = library.OpcodeClassNames[
        op.tile_description.math_instruction.opcode_class
    ]
    layout = op.layout_name()
    align_ab = op.A.alignment
    align_c = op.C.alignment
    prefix = ""
    if op.prefix != "":
        kernel_schedule = library.KernelScheduleSuffixes[op.kernel_schedule]
        epilogue_schedule = library.EpilogueScheduleSuffixes[op.epilogue_schedule]
        prefix = f"{op.prefix}{kernel_schedule}{epilogue_schedule}"
    name = KERNEL_KEY_TEMPLATE.render(
        prefix=prefix,
        threadblock=threadblock,
        extended_name=extended_name,
        opcode_class_name=opcode_class_name,
        layout=layout,
        align_ab=align_ab,
        align_c=align_c,
    )
    return name.replace("\n", "")


def emit_instance(
    op,
    for_profiler,
    f_instance_convertor=sparse_gemm_instance,
    emit_kernel=False,
    func_attrs=None,
):
    import cutlass_lib

    cutlass_3x = op.gemm_kind == cutlass_lib.library.GemmKind.Universal3x
        
    emitter = cutlass_lib.gemm_operation.EmitSparseGemmInstance()

    op_def = emitter.emit(op)
    op_def = f_instance_convertor(
        op_def=op_def,
        func_attrs=func_attrs,
        for_profiler=for_profiler,
        cutlass_3x=cutlass_3x,
    )

    return op_def
'''
// Gemm operator cutlass_tensorop_s16832spgemm_f16_128x128_64x6_nn_align8
using Operation_cutlass_tensorop_s16832spgemm_f16_128x128_64x6_nn_align8 = cutlass::gemm::device::SparseGemm<
    cutlass::half_t, cutlass::layout::RowMajor,
    cutlass::half_t, cutlass::layout::ColumnMajor,
    cutlass::half_t, cutlass::layout::RowMajor,
    float,
    cutlass::arch::OpClassTensorOp,
    cutlass::arch::Sm80,
    cutlass::gemm::GemmShape<128, 128, 64>,
    cutlass::gemm::GemmShape<64, 64, 64>,
    cutlass::gemm::GemmShape<16, 8, 32>,
    cutlass::epilogue::thread::LinearCombination<
        cutlass::half_t,
        4,
        float,
        float
    >,
    cutlass::gemm::threadblock::GemmIdentityThreadblockSwizzle<8>,
    2,
    8,
    8>;
'''

def extract_config(
    f_proc_op,
    f_kernel_name=kernel_name,
    include_cutlass_3x_ops=False,
):
    import cutlass_lib

    op_kind = cutlass_lib.library.OperationKind.Gemm
    gemm_kinds = {cutlass_lib.library.GemmKind.Sparse}
    gemm_ops = OrderedDict()
    extract_ops = list(Target.current()._operators[op_kind].items())

    for _, value in extract_ops:
        op = value[0]
        if op.gemm_kind in gemm_kinds:
            ret = f_proc_op(op)
            if len(ret) > 0:
                for op_inst in ret:
                    key = f_kernel_name(op_inst)
                    gemm_ops[key] = op_inst
    return gemm_ops


def extract_config_name(
    config,
    cutlass_3x=False,
):
    if cutlass_3x:
        pattern = re.compile(r"\s*struct\s(.*?)\s:")
        decl = [line for line in config.split("\n") if "struct " in line][-1]
    else:
        pattern = re.compile(r"\s*using\s(.*?)\s=")
        decl = config.split("\n")[2]
    match = pattern.match(decl)
    if match is None:
        raise RuntimeError("Invalid config: \n" + config)
    return match.groups()[0]


def gen_function(
    func_attrs,
    src_template,
    exec_cond_template,
    problem_args,
    input_ndims,
    weight_ndims,
    meta_ndims,
    output_ndims,
    dim_info_dict,
    f_instance_convertor=sparse_gemm_instance,
    emit_kernel=False,
    support_split_k=False,
    input_addr_calculator="",
    output_addr_calculator="",
    extra_code="",
    problem_args_cutlass_3x="",
):
    backend_spec = CUDASpec()
    elem_input_type = backend_spec.dtype_to_lib_type(
        func_attrs["inputs"][0]._attrs["dtype"]
    )
    elem_output_type = backend_spec.dtype_to_lib_type(
        func_attrs["outputs"][0]._attrs["dtype"]
    )
    func_name = func_attrs["name"]
    exec_path = func_attrs["exec_path"]
    op_instance = func_attrs["op_instance"]
    inst_def_flag = set()
    instances = {}
    instance_decl = ""
    exec_cond_to_cutlass_3x = {}
    for exec_item in exec_path.values():
        fname = "f" + sha1(exec_item.exec_cond.encode()).hexdigest()
        algo = exec_item.algo
        cutlass_3x = algo.startswith("cutlass3x")
        if algo not in inst_def_flag:
            config = emit_instance(
                op_instance[algo],
                for_profiler=False,
                f_instance_convertor=f_instance_convertor,
                emit_kernel=emit_kernel,
                func_attrs=func_attrs,
            )
            inst_def_flag.add(algo)
        else:
            config = ""
        # if "spgemm" in algo:
        #     instance_template = INSTANCE_TEMPLATE_SPARSE
        # elif cutlass_3x:
        #     instance_template = INSTANCE_TEMPLATE_CUTLASS_3X
        # else:
        instance_template = INSTANCE_TEMPLATE
        inst = instance_template.render(
            config=config,
            name=fname,
            config_name=extract_config_name(
                config,
                cutlass_3x=cutlass_3x,
            ),
        )
        instances[exec_item.exec_cond] = inst
        exec_cond_to_cutlass_3x[exec_item.exec_cond] = cutlass_3x
        instance_decl += inst
    shape_eval_func = gemm_sparse_common.gen_shape_eval_code(
        indent=1, dtype="int64_t", dim_info_dict=dim_info_dict, is_ptr=True
    )

    exec_paths = ""
    for exec_cond in instances:
        fname = "f" + sha1(exec_cond.encode()).hexdigest()
        cutlass_3x = exec_cond_to_cutlass_3x[exec_cond]
        program = EXEC_TEMPLATE.render(
            indent="    ",
            instance=fname,
            # need to omit irrelevant problem_args here as in
            # non-templated function both CUTLASS 2.x and 3.x
            # code branches are syntactically checked
            problem_args=(problem_args if not cutlass_3x else ""),
            # problem_args_cutlass_3x=(problem_args_cutlass_3x if cutlass_3x else ""),
            problem_args_cutlass_3x=problem_args,
            support_split_k=support_split_k,
        )
        exec_inst = exec_cond_template.render(
            indent="  ",
            #cond=exec_cond,
            cond="true",
            program=program,                                                                      
        )
        exec_paths += exec_inst
    input_output_checks = INPUT_OUTPUT_CHECKS_TEMPLATE.render(
        input_ndims=input_ndims,
        weight_ndims=weight_ndims,
        meta_ndims=meta_ndims,
        output_ndims=output_ndims,
    )
    metadata_code = "\n".join([
        "  // metadata pointer & stride for 2:4 sparsity",
        "  void* m_ptr = m_ptr;",
    ])
    return src_template.render(
        instances=instance_decl,
        function_name=func_name,
        dtype="cutlass::half_t",
        shape_eval=shape_eval_func,
        input_addr_calculator=input_addr_calculator,
        output_addr_calculator=output_addr_calculator,
        input_output_checks=input_output_checks,
        metadata_code=metadata_code,
        exec_paths=exec_paths,
        input_ndims=input_ndims,
        weight_ndims=weight_ndims,
        meta_ndims=meta_ndims,
        output_ndims=output_ndims,
        support_split_k=support_split_k,
        has_d=has_d(func_attrs),
        has_d1=has_d1(func_attrs),
        extra_code=extra_code,
        elem_input_type=elem_input_type,
        elem_output_type=elem_output_type,
    )


def build_profiler(file_pairs):
    target = Target.current()
    if target.disable_profiler_codegen():
        file_pairs = []
    elif target.use_dummy_profiling_results():
        # if it is circle CI only random build 2 profilers
        random.shuffle(file_pairs)
        file_pairs = file_pairs[:2]
    return file_pairs


def add_profiler(file_pairs, workdir, op_type, output_name, code):
    prefix = os.path.join(workdir, "profiler", op_type)
    if not os.path.exists(prefix):
        os.makedirs(prefix)

    obj_path = os.path.join(prefix, output_name)
    if os.path.exists(obj_path):
        return

    if isinstance(code, dict):
        # multi-source profiler
        src_paths = []
        for src_name, src_code in code.items():
            # create each source file separately
            src_path = os.path.join(prefix, src_name + ".cu")
            with open(src_path, "w") as f:
                f.write(src_code)
            src_paths.append(src_path)
        # add multiple src paths to file_pairs
        file_pairs.append((src_paths, obj_path))
    else:
        # single-source profiler
        src_path = os.path.join(prefix, output_name + ".cu")
        with open(src_path, "w") as f:
            f.write(code)
        # add single src path to file_pairs
        file_pairs.append((src_path, obj_path))


def has_tma_epilogue(op):
    """Check whether the op is CUTLASS 3.x and has a TMA epilogue schedule."""
    import cutlass_lib

    result = False
    if op.gemm_kind == cutlass_lib.library.GemmKind.Universal3x:
        epilogue_schedule_str = str(op.epilogue_schedule).split(".")[-1]
        result = epilogue_schedule_str.lower().startswith("tma")

    return result


def filter_cutlass_3x_ops(op_instance, func_attrs):
    """Filter out CUTLASS 3.x ops with incompatible alignment requirements.

    The CUTLASS 3.x ops have stricter alignment requirements compared to
    the CUTLASS 2.x ops (due to TMA). These alignment requirements are used
    to initially filter them out in the `function_filter` below. However, the
    required alignments of the GEMM op inputs and outputs may change due to
    TensorAccessor-related optimizations, which are introduced to the model
    graph *after* the initial filtering.

    In this function, the (possible) TA-related alignment updates are checked
    once again and the CUTLASS 3.x ops not satisfying these requirements are
    filtered out. Importantly, due to input/output alignment flexibilit of the
    CUTLASS 2.x ops, their alignment requirements are corrected using the
    TA-imposed alignments in the `update_alignments_in_gemm_instance` function
    above. But this correction is not possible for the CUTLASS 3.x ops, as they
    won't work with the lower alignment values. That's why the CUTLASS 3.x ops
    are filtered out by this function in such cases.
    """
    import cutlass_lib

    a_alignment, b_alignment, epilogue_alignment = get_tensor_accessor_alignments(
        func_attrs
    )

    result_2x, result_3x = {}, {}
    for op_name, op in op_instance.items():
        if op.gemm_kind == cutlass_lib.library.GemmKind.Universal3x:
            if (
                op.A.alignment <= a_alignment
                and op.B.alignment <= b_alignment
                and op.C.alignment <= epilogue_alignment
            ):
                result_3x[op_name] = op
        else:
            result_2x[op_name] = op

    has_ops_with_tma_epilogue = False
    if result_3x:
        for op in result_3x.values():
            if has_tma_epilogue(op):
                has_ops_with_tma_epilogue = True
                break

        if has_ops_with_tma_epilogue:
            # when there are ops with TMA epilogue, keep only those
            # for better performance / shorter profiler compilation time
            result_3x = {
                op_name: op for op_name, op in result_3x.items() if has_tma_epilogue(op)
            }

    return {
        # CUTLASS 3.x kernels can cause power throttling:
        # we want to generate the 2.x kernels first to avoid
        # performance side effects caused by the 3.x kernels
        **result_2x,
        **result_3x,
    }, has_ops_with_tma_epilogue


def gen_profiler(
    func_attrs,
    workdir,
    profiler_filename,
    dim_info_dict,
    src_template,
    problem_args_template,
    args_parser_template,
    support_split_k=False,
    input_addr_calculator="",
    output_addr_calculator="",
    bias_ptr_arg=None,
    extra_code="",
    problem_args_template_cutlass_3x=None,
):
    import cutlass_lib

    op_type = func_attrs["op"]
    op_instance = func_attrs["op_instance"]
    op_instance, op_has_tma_epilogue = filter_cutlass_3x_ops(op_instance, func_attrs)

    backend_spec = CUDASpec()
    elem_input_type = backend_spec.dtype_to_lib_type(
        func_attrs["inputs"][0]._attrs["dtype"]
    )
    elem_output_type = backend_spec.dtype_to_lib_type(
        func_attrs["outputs"][0]._attrs["dtype"]
    )
    elem_type = backend_spec.dtype_to_backend_type(
        func_attrs["inputs"][0]._attrs["dtype"]
    )
    ndims = 2
    adims = ["&a_dim" + str(i) for i in range(ndims)]
    bdims = ["&b_dim" + str(i) for i in range(ndims)]
    mdims = ["&m_dim" + str(i) for i in range(ndims)]
    cdims = ["&c_dim" + str(i) for i in range(ndims)]
    shape_func = gemm_sparse_common.gen_shape_eval_code(
        indent=2, dtype="int64_t", dim_info_dict=dim_info_dict, is_ptr=True
    )

    has_bias = bias_ptr_arg is not None
    instance_name_base = "GemmInstance"
    exec_program = EXEC_TEMPLATE.render(
        indent="  ",
        instance=instance_name_base,
        is_profiler=True,
        support_split_k=support_split_k,
        problem_args=problem_args_template.render(
            elem_input_type=elem_input_type,
            elem_output_type=elem_output_type,
        ),
        problem_args_cutlass_3x=(
            problem_args_template_cutlass_3x.render(
                elem_input_type=elem_input_type,
                elem_output_type=elem_output_type,
                has_tma_epilogue=op_has_tma_epilogue,
            )
            if problem_args_template_cutlass_3x is not None
            else ""
        ),
    )
    input_output_checks = INPUT_OUTPUT_CHECKS_TEMPLATE.render(
        input_ndims=ndims,
        weight_ndims=ndims,
        meta_ndims=ndims,
        output_ndims=ndims,
    )

    function_name = "gemm_sparse"
    instances = []
    benchmark_instances = []
    for instance_idx, (op_name, op) in enumerate(op_instance.items()):
        config = emit_instance(op, func_attrs=func_attrs, for_profiler=True)
        instance_name = f"{instance_name_base}_{instance_idx}"
        gemm_op = f"gemm_sparse_op_{instance_idx}"
        cutlass_3x = op.gemm_kind == cutlass_lib.library.GemmKind.Universal3x
        instance_template = (
            INSTANCE_TEMPLATE_CUTLASS_3X if cutlass_3x else INSTANCE_TEMPLATE
        )
        instance = instance_template.render(
            config_name=extract_config_name(
                config,
                cutlass_3x=cutlass_3x,
            ),
            name=instance_name,
            config=config,
        )
        benchmark_instance = BENCHMARK_INSTANCE_TEMPLATE.render(
            indent="  ",
            instance_name=instance_name,
            gemm_op=gemm_op,
            gemm_op_name=op_name,
            func_name=f"benchmark_{function_name}",
            support_split_k=support_split_k,
            split_k="split_k",
            adims=adims,
            bdims=bdims,
            mdims=mdims,
            cdims=cdims,
        )
        instances.append(instance)
        benchmark_instances.append(benchmark_instance)
    # TODO: Render args_parse by caller.
    args_parse = (
        args_parser_template
        if isinstance(args_parser_template, str)
        else args_parser_template.render()
    )
    metadata_code = "\n".join([
        "  // metadata pointer & stride for 2:4 sparsity",
        "  void* m_ptr = m_ptr;",
    ])
    op_func = src_template.render(
        is_profiler=True,
        instances="\n".join(instances),
        function_name=function_name,
        dtype="cutlass::half_t",
        input_ndims=ndims,
        weight_ndims=ndims,
        meta_ndims=ndims,
        output_ndims=ndims,
        shape_eval=shape_func,
        input_output_checks=input_output_checks,
        metadata_code=metadata_code,
        exec_paths=exec_program,
        input_addr_calculator=input_addr_calculator,
        output_addr_calculator=output_addr_calculator,
        support_split_k=support_split_k,
        has_d=has_d(func_attrs),
        has_d1=has_d1(func_attrs),
        extra_code=extra_code,
        elem_input_type=elem_input_type,
        elem_output_type=elem_output_type,
    )
    benchmark_adims = ["a_dim" + str(i) for i in range(ndims)]
    benchmark_bdims = ["b_dim" + str(i) for i in range(ndims)]
    benchmark_mdims = ["m_dim" + str(i) for i in range(ndims)]
    benchmark_cdims = ["c_dim" + str(i) for i in range(ndims)]
    func_call = FUNC_CALL_TEMPLATE.render(
        is_profiler=True,
        func_name=function_name,
        a_ptr="memory_pool->RequestTensorByIdx(0)",
        b_ptr="memory_pool->RequestTensorByIdx(1)",
        metadata_ptr="memory_pool->RequestTensorByIdx(2)",
        has_bias=has_bias,
        bias_ptr=bias_ptr_arg,
        c_ptr="memory_pool->RequestTensorByIdx(3)",
        split_k="split_k",
        adims=benchmark_adims,
        bdims=benchmark_bdims,
        mdims=benchmark_mdims,
        cdims=benchmark_cdims,
    )
    tensor_decl = TENSOR_DECL_TEMPLATE.render(
        elem_input_type=elem_input_type,
        elem_output_type=elem_output_type,
        has_bias=has_bias,
    )
    code = PROFILER_TEMPLATE.render(
        op_func=op_func,
        has_bias=has_bias,
        has_d=has_d(func_attrs),
        support_split_k=support_split_k,
        args_parse=args_parse,
        function_name=function_name,
        input_ndims=ndims,
        weight_ndims=ndims,
        meta_ndims=ndims,
        output_ndims=ndims,
        func_call=func_call,
        name=instance_name_base,
        tensor_decl=tensor_decl,
        benchmark_instances="\n".join(benchmark_instances),
        elem_type=elem_type,
    )
    # FIXME: remove file_pairs once we have make -j ready for building
    # an entire graph
    file_pairs = []
    add_profiler(file_pairs, workdir, op_type, profiler_filename, code)
    # build
    return build_profiler(file_pairs)


def gen_local_dim_defs(func_attrs, indent="  "):
    """
    used together with input TensorAccessor to access a strided input
    """
    if "input_accessors" not in func_attrs:
        return ""

    dims = {}
    for input_idx, input_accessor in enumerate(func_attrs["input_accessors"]):
        if not input_accessor.is_from_strided_tensor:
            continue
        original_shape = input_accessor.original_shapes
        for idx, dim in enumerate(original_shape):
            # skip dynamic dims
            if isinstance(dim, IntImm):
                input_shape = func_attrs["inputs"][input_idx]._attrs["shape"]
                if idx < len(input_shape):
                    name = input_shape[idx]._attrs["name"]
                    if name in dims:
                        assert dims[name] == dim.value(), "bmm inputs shape mismatch"
                    else:
                        dims[name] = dim.value()
    return DIM_DEFS_TEMPLATE.render(dims=dims, indent=indent)


def gen_function_call(func_attrs, metadata_ptr_arg, metadata_stride_arg, bias_ptr_arg=None, indent="  "):
    a = func_attrs["inputs"][0]
    ashapes = func_attrs["input_accessors"][0].original_shapes
    b = func_attrs["inputs"][1]
    bshapes = func_attrs["input_accessors"][1].original_shapes
    m = func_attrs["inputs"][2]
    mshapes = func_attrs["input_accessors"][2].original_shapes
    c = func_attrs["outputs"][0]
    cshapes = func_attrs["output_accessors"][0].original_shapes
    has_bias = bias_ptr_arg is not None
    # overwrite the global defs if we have input TensorAccessor
    local_dim_defs = gen_local_dim_defs(func_attrs, indent=indent)
    adims = ["&" + dim._attrs["name"] for dim in ashapes]
    bdims = ["&" + dim._attrs["name"] for dim in bshapes]
    mdims = ["&" + dim._attrs["name"] for dim in mshapes]
    cdims = ["&" + dim._attrs["name"] for dim in cshapes]
    return FUNC_CALL_TEMPLATE.render(
        local_dim_defs=local_dim_defs,
        func_name=func_attrs["name"],
        a_ptr=a._attrs["name"],
        b_ptr=b._attrs["name"],
        metadata_ptr=metadata_ptr_arg,
        has_bias=has_bias,
        bias_ptr=bias_ptr_arg,
        c_ptr=c._attrs["name"],
        split_k=func_attrs["split_k"],
        adims=adims,
        bdims=bdims,
        mdims=mdims,
        cdims=cdims,
        indent=indent,
    )


def default_fproc(
    *, op, a_layout, b_layout, c_layout, dtype, epilogue_name, permute_layout=None
):
    import copy

    import cutlass_lib

    backend_spec = CUDASpec()

    ret = []
    # skip simt kernels
    if (
        op.tile_description.math_instruction.opcode_class
        == cutlass_lib.library.OpcodeClass.Simt
    ):
        return ret
    data_type = backend_spec.dtype_to_lib_type(dtype)
    if data_type == "float":
        if (
            op.tile_description.math_instruction.element_a
            != cutlass_lib.library.DataType.f32
            and op.tile_description.math_instruction.element_a
            != cutlass_lib.library.DataType.tf32
        ):
            return ret
    acc_type = cutlass_lib.library.DataType.f32

    if (
        "no_tf32" in Target.current()._kwargs
        and data_type == "float"
        and Target.current()._kwargs["no_tf32"]
    ):
        if (
            op.tile_description.math_instruction.element_a
            == cutlass_lib.library.DataType.tf32
        ):
            return ret

    # check target use fp16 acc
    if "use_fp16_acc" in Target.current()._kwargs and data_type == "cutlass::half_t":
        if Target.current()._kwargs["use_fp16_acc"]:
            acc_type = cutlass_lib.library.DataType.f16

    # For column-major C layouts, filter out GEMM tiling configs introducted by
    # extra_cutlass_generator.py - those will cause a build error.
    threadblock_mxn = op.tile_description.threadblock_shape[:2]
    is_nonstandard_theadblock_shape = threadblock_mxn == [128, 32]
    filter_extra_tile_configs = (
        is_nonstandard_theadblock_shape
        and c_layout == cutlass_lib.library.LayoutType.ColumnMajor
    )

    if (
        cutlass_lib.library.DataTypeTag[op.A.element] == data_type
        and cutlass_lib.library.DataTypeTag[op.B.element] == data_type
        and cutlass_lib.library.DataTypeTag[op.C.element] == data_type
        and cutlass_lib.library.DataTypeTag[op.D.element] == data_type
        and op.accumulator_type() == acc_type
        and op.A.layout == a_layout
        and op.B.layout == b_layout
        and not filter_extra_tile_configs
    ):
        op = copy.deepcopy(op)

        # set output major
        op.C.layout = c_layout
        op.D.layout = c_layout

        # set epilogue
        op.epilogue_functor = cutlass_lib.library.EpilogueFunctorName[epilogue_name]
        op.element_epilogue = acc_type
        if (
            op.gemm_kind == cutlass_lib.library.GemmKind.Universal3x
            and op.epilogue_functor
            != cutlass_lib.library.EpilogueFunctor.LinearCombination
        ):
            # need to substitute the epilogue schedule with
            # the one parameterized by the epilogue functor
            if op.epilogue_schedule in (
                cutlass_lib.library.EpilogueScheduleType.TmaWarpSpecialized,
                cutlass_lib.library.EpilogueScheduleType.TmaWarpSpecializedCooperative,
            ):
                op.epilogue_schedule = cutlass_lib.library.EpilogueScheduleMapping[
                    op.epilogue_schedule
                ][op.epilogue_functor]
            else:
                # epilogue functor parameterization unavailable
                # for the rest of epilogue schedule types
                return ret

        # set permute layout
        if permute_layout is not None:
            op.permute_layout = cutlass_lib.library.EpiloguePermuteLayoutName[
                permute_layout
            ]

        # set C and D alignment
        alignments = alignment.get_alignments(dtype)
        for i in alignments:
            if has_tma_epilogue(op) and i != max(alignments):
                # TMA epilogues only support max. output alignment
                continue
            op = copy.deepcopy(op)
            op.C.alignment = i
            op.D.alignment = i
            ret.append(op)

    return ret


def make_fproc(
    func_attrs,
    layout,
    include_cutlass_3x_ops=False,
):
    """
    This function sets a callback for processing the epilogue of the kernel
    associated with func_attrs.
    """

    def fproc(op):
        a_layout, b_layout, c_layout = layout.cutlass_lib_layouts()
        return default_fproc(
            op=op,
            a_layout=a_layout,
            b_layout=b_layout,
            c_layout=c_layout,
            dtype=func_attrs["inputs"][0].dtype(),
            epilogue_name=func_attrs["epilogue"],
        )

    func_attrs["op_instance"] = extract_config(
        f_proc_op=fproc,
        include_cutlass_3x_ops=include_cutlass_3x_ops,
    )
    


def function_filter(cfg, func_attrs, ab_alignment):
    """Generates function filter.

    Parameters
    ----------
    cfg: str
        The filename generated for profiler.
    func_attrs : Dict
        Stores the operation attributes.
    ab_alignment:
        Input alignments.

    Returns
    -------
    bool
        If input cfg should be filtered.
    """
    # example:
    # cfg="cutlass_tensorop_f16_s16816gemm_f16_128x32_64x4_nn_align_8_8"
    tmp = cfg.split("_")
    align_c = int(tmp[-1])
    align_ab = int(tmp[-2])
    if align_c != func_attrs["epilogue_alignment"]:
        return False
    if align_ab != ab_alignment:
        return False
    return True
