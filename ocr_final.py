"""
DeepSeek-OCR-2 - FINAL WORKING VERSION
Extracts data from images and saves to JSON
"""

import os, sys, json, torch, re, io
from contextlib import redirect_stdout, redirect_stderr
from transformers import AutoModel, AutoTokenizer

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(PROJECT_DIR, "models", "DeepSeek-OCR-2")

def load_model():
    print("Loading model...", end=" ")
    if not torch.cuda.is_available():
        print("ERROR: No CUDA!"); sys.exit(1)
    
    tok = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    
    try:
        mdl = AutoModel.from_pretrained(MODEL_PATH, attn_implementation='flash_attention_2',
                                         trust_remote_code=True, use_safetensors=True,
                                         torch_dtype=dtype, low_cpu_mem_usage=True)
    except:
        mdl = AutoModel.from_pretrained(MODEL_PATH, attn_implementation='eager',
                                         trust_remote_code=True, use_safetensors=True,
                                         torch_dtype=dtype, low_cpu_mem_usage=True)
    
    print("Done!"); return mdl.eval().cuda(), tok

def clean_table(html):
    """Extract table data from HTML"""
    rows = []
    for tr in re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL):
        cells = [c.strip().replace('\\(','').replace('\\)','').replace('$ ','$') 
                 for c in re.findall(r'<td>(.*?)</td>', tr)]
        if any(cells): rows.append(cells)
    return rows

def extract_from_output(captured_output):
    """Extract the tagged data from captured stdout and convert to readable format"""
    
    # First extract raw sections
    raw_sections = []
    title = ""
    
    # Get title
    for line in captured_output.split('\n'):
        if line.strip().startswith('## ') and not title:
            title = line.replace('#', '').strip()
            break
    
    # Find all sections - split by <|ref|>
    parts = captured_output.split('<|ref|>')
    
    for part in parts[1:]:
        if '<|/ref|>' not in part:
            continue
            
        # Extract type
        type_end = part.find('<|/ref|>')
        sec_type = part[:type_end].strip()
        
        # Extract bbox (we'll ignore this in final output)
        if '<|det|>[[' not in part or ']]<|/det|>' not in part:
            continue
        
        # Extract content
        content_start = part.find(']]<|/det|>') + 11
        content = part[content_start:].strip()
        
        # Stop at next section
        if '<|ref|>' in content:
            content = content.split('<|ref|>')[0].strip()
        
        # Clean content
        content = re.sub(r'^##\s*', '', content, flags=re.MULTILINE)
        
        raw_sections.append({
            "type": sec_type,
            "content": content
        })
    
    # Now convert to readable format
    result = {
        "document_title": title,
        "content": []
    }
    
    current_section = None
    
    for item in raw_sections:
        item_type = item["type"]
        content = item["content"]
        
        if item_type == "sub_title":
            # Start new section
            current_section = {
                "heading": content,
                "items": []
            }
            result["content"].append(current_section)
        
        elif item_type == "table":
            # Parse table and convert to financial_table format
            table_data = clean_table(content)
            
            if table_data and len(table_data[0]) == 2:
                # Two-column financial table
                table_obj = {
                    "type": "financial_table",
                    "entries": []
                }
                
                for row in table_data:
                    if len(row) == 2:
                        label = row[0].strip()
                        value = row[1].strip()
                        
                        if label and value:
                            table_obj["entries"].append({
                                "label": label,
                                "amount": value
                            })
                        elif label:  # Header row
                            table_obj["entries"].append({
                                "label": label,
                                "amount": None
                            })
                
                if current_section:
                    current_section["items"].append(table_obj)
                else:
                    result["content"].append(table_obj)
            else:
                # Generic table
                table_obj = {
                    "type": "table",
                    "data": table_data
                }
                if current_section:
                    current_section["items"].append(table_obj)
                else:
                    result["content"].append(table_obj)
        
        elif item_type == "text":
            # Regular text
            if content:
                text_obj = {"type": "text", "value": content}
                if current_section:
                    current_section["items"].append(text_obj)
                else:
                    result["content"].append(text_obj)
    
    return result

# MAIN
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_final.py image.jpg [output.json]")
        sys.exit(1)
    
    img = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(img):
        print(f"ERROR: {img} not found!"); sys.exit(1)
    
    print(f"Processing: {img}")
    model, tokenizer = load_model()
    
    # Capture stdout to get the printed output
    stdout_capture = io.StringIO()
    
    with torch.no_grad():
        with redirect_stdout(stdout_capture):
            model.infer(tokenizer, prompt="<image>\n<|grounding|>Convert the document to markdown.",
                       image_file=img, output_path=os.path.join(PROJECT_DIR, "temp"), base_size=1024,
                       image_size=768, crop_mode=True, save_results=False)
    
    # Get captured output
    captured = stdout_capture.getvalue()
    
    # Extract data from the captured output
    data = extract_from_output(captured)
    js = json.dumps(data, indent=2, ensure_ascii=False)
    
    if out:
        with open(out, 'w', encoding='utf-8') as f: f.write(js)
        print(f"✓ Saved: {out}")
    else:
        print("\n" + "="*70)
        print(js)
        print("="*70)
