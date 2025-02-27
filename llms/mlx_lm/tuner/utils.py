import os

import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_unflatten

from .lora import LoRALinear


def apply_lora_layers(model: nn.Module, adapter_file: str) -> nn.Module:
    """
    Apply LoRA layers to the model.

    Args:
        model (nn.Module): The neural network model.
        adapter_file (str): Path to the adapter configuration file.

    Returns:
        nn.Module: The updated model with LoRA layers applied.
    """
    if not os.path.exists(adapter_file):
        raise FileNotFoundError(f"The adapter file does not exist: {adapter_file}")

    adapters = list(mx.load(adapter_file).items())

    linear_replacements = []
    lora_layers = set(
        [name.replace(".lora_a", "").replace(".lora_b", "") for name, _ in adapters]
    )
    for name, module in model.named_modules():
        if name in lora_layers:
            replacement_module = LoRALinear.from_linear(module)
            linear_replacements.append((name, replacement_module))

    model.update_modules(tree_unflatten(linear_replacements))
    return model


def dequantize(model: nn.Module) -> nn.Module:
    """
    Dequantize the quantized linear layers in the model.

    Args:
        model (nn.Module): The model with quantized linear layers.

    Returns:
        nn.Module: The model with dequantized layers.
    """
    de_quantize_layers = []
    for n, m in model.named_modules():
        if isinstance(m, nn.QuantizedLinear):
            bias = "bias" in m
            weight = m.weight
            weight = mx.dequantize(
                weight,
                m.scales,
                m.biases,
                m.group_size,
                m.bits,
            ).astype(mx.float16)
            output_dims, input_dims = weight.shape
            linear = nn.Linear(input_dims, output_dims, bias=bias)
            linear.weight = weight
            if bias:
                linear.bias = m.bias
            de_quantize_layers.append((n, linear))
    if len(de_quantize_layers) > 0:
        model.update_modules(tree_unflatten(de_quantize_layers))
    return model
