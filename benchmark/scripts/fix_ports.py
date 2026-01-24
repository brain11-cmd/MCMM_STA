#!/usr/bin/env python3
import re
import sys

def fix_escaped_ports(content):
    # 替换所有转义标识符格式
    # 1. \name.subname[index] -> name_subname_index
    def replace_complex(match):
        full_name = match.group(1)
        index = match.group(2)
        # 将点号替换为下划线
        clean_name = full_name.replace('.', '_')
        return f'{clean_name}_{index}'
    
    # 匹配 \identifier.subidentifier[index] 格式（包含点号）
    content = re.sub(r'\\([\w.]+)\[(\d+)\]', replace_complex, content)
    
    # 2. \name[index] -> name_index (简单格式)
    def replace_simple(match):
        name = match.group(1)
        index = match.group(2)
        return f'{name}_{index}'
    
    # 匹配 \identifier[index] 格式（不包含点号，避免重复处理）
    content = re.sub(r'\\(\w+)\[(\d+)\]', replace_simple, content)
    
    # 3. 处理单独的转义标识符（没有索引的）
    # \name.subname -> name_subname
    content = re.sub(r'\\([\w.]+)(?![\[\w])', lambda m: m.group(1).replace('.', '_'), content)
    
    return content

if __name__ == '__main__':
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = fix_escaped_ports(content)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed ports in {input_file} -> {output_file}")

