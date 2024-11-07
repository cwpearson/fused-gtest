import os
import re
from pathlib import Path
from typing import Set, Dict, List
from dataclasses import dataclass
from enum import Enum, auto
from sys import stderr

class FileType(Enum):
    HEADER = auto()
    SOURCE = auto()
    UNKNOWN = auto()

@dataclass
class ProcessedFile:
    path: Path
    content: str
    type: FileType

def get_file_type(path: Path) -> FileType:
    """Determine if file is header or source based on extension."""
    ext = path.suffix.lower()
    if ext in ['.h', '.hpp', '.hxx', '.hh']:
        return FileType.HEADER
    elif ext in ['.c', '.cpp', '.cxx', '.cc']:
        return FileType.SOURCE
    return FileType.UNKNOWN

class CppFusioner:
    def __init__(self, include_paths: List[str], inline_headers=False, inline_sources=False):
        self.include_paths = [Path(p) for p in include_paths]
        self.processing_stack: Set[Path] = set()  # For circular dependency detection
        self.inline_headers = inline_headers
        self.inline_sources = inline_sources
        self.already_inlined: Set[Path] = set()
        

    
    def find_include_file(self, include_name: str, current_dir: Path) -> Path | None:
        """Search for included file in current directory and include paths."""
        # First check relative to current file
        local_path = current_dir / include_name
        if local_path.exists():
            return local_path
            
        # Then check include paths
        for include_path in self.include_paths:
            full_path = include_path / include_name
            if full_path.exists():
                return full_path
                
        return None
    
    def process_file(self, file_path: Path) -> ProcessedFile:
        """Process a single file and its includes recursively."""
        abs_path = file_path.resolve()
        
           
        # Check for circular dependencies
        if abs_path in self.processing_stack:
            raise Exception(f"Circular dependency detected: {abs_path}")
            
        self.processing_stack.add(abs_path)
        
        try:
            with open(abs_path, 'r') as f:
                content = f.read()
                
            file_type = get_file_type(abs_path)
            processed_lines = []
            
            # Process line by line
            for line in content.split('\n'):
                include_match = re.match(r'#include\s*[<"]([^>"]+)[>"]', line)
                if include_match:
                    include_name = include_match.group(1)

                    # Keep system includes
                    if '<' in line:
                        print(f"preserve system include {include_name} in {file_path}", file=stderr)
                        processed_lines.append(line)
                        continue

                    # Find and process local include
                    include_path = self.find_include_file(include_name, abs_path.parent)

                    if include_path in self.already_inlined:
                        print(f"already inlined {include_path} when processing {file_path}", file=stderr)
                        continue

                    if include_path:

                        included_file_type = get_file_type(include_path)

                        if self.inline_headers and included_file_type == FileType.HEADER:
                            included_file = self.process_file(include_path)
                            print(f"inline header {include_name}", file=stderr)
                            processed_lines.append(f"// Inlined from: {include_path}")
                            processed_lines.append(included_file.content)
                            self.already_inlined.add(include_path)
                        elif self.inline_sources and (included_file_type == FileType.SOURCE or include_name == "src/gtest-internal-inl.h" or include_name == "gtest/gtest-spi.h"):
                            included_file = self.process_file(include_path)
                            print(f"inline source {include_name}", file=stderr)
                            processed_lines.append(f"// Inlined from: {include_path}")
                            processed_lines.append(included_file.content)
                            self.already_inlined.add(include_path)
                        elif include_name.startswith("gtest/") and include_name != "gtest/gtest.h":
                            print(f"skipping {include_name} when processing {file_path}", file=stderr)
                            processed_lines.append("//" + line)
                        else:
                            print(f"not inlining {include_name} when processing {file_path}", file=stderr)
                            processed_lines.append(line)
                    else:
                        # Include not found, keep original line
                        print(f"could not find {line}", file=stderr)
                        processed_lines.append(line)
                else:
                    processed_lines.append(line)
            
            processed = ProcessedFile(
                path=abs_path,
                content='\n'.join(processed_lines),
                type=file_type
            )
            
            return processed
            
        finally:
            self.processing_stack.remove(abs_path)
    
    def fuse_file(self, input_file: str, output_file: str):
        """Process input file and write fused output."""
        input_path = Path(input_file)

        processed = self.process_file(input_path)
        
        output_content = []
        if processed.type == FileType.HEADER:
            # Add header guard
            guard_name = f"FUSED_{input_path.stem.upper()}_H"
            output_content.extend([
                f"#ifndef {guard_name}",
                f"#define {guard_name}",
                "",
                processed.content,
                "",
                f"#endif  // {guard_name}"
            ])
        else:
            output_content.append(processed.content)
            
        with open(output_file, 'w') as f:
            f.write('\n'.join(output_content))

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python fusioner.py <input_file> <output_file> [include_path1] [include_path2] ...")
        sys.exit(1)
        
    input_file = Path(sys.argv[1])
    output_file = sys.argv[2]
    include_paths = sys.argv[3:] if len(sys.argv) > 3 else ['.']
    
    file_type = get_file_type(input_file)

    fusioner = CppFusioner(include_paths, inline_headers=(file_type == FileType.HEADER), inline_sources=(file_type == FileType.SOURCE))
    fusioner.fuse_file(input_file, output_file)