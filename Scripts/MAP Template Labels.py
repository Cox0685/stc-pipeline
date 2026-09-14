#!/usr/bin/env python
# coding: utf-8

"""
Add Template Categories to GLD Templates
Reads gld_templates.csv, adds template_category column based on mapping from JSON
"""

import os
import json
import pandas as pd
from typing import Dict, List, Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
GLD_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
TEMPLATE_JSON_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP\template_att.json"

# ============================================================================
# LOAD TEMPLATE MAPPING FROM JSON
# ============================================================================

def load_template_mapping(json_path: str) -> tuple:
    """
    Load template categories from JSON file.
    Returns (id_mapping, name_pattern_mapping)
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Build ID-based mapping
    id_mapping = {}
    name_pattern_mapping = {}
    
    for template in data.get('templates', []):
        template_id = template.get('id')
        template_name = template.get('name')
        categories = template.get('categories', [])
        
        if template_id:
            id_mapping[template_id] = {
                'name': template_name,
                'categories': categories
            }
        
        # Also add name pattern mapping for fallback
        if template_name:
            name_pattern_mapping[template_name] = categories
    
    return id_mapping, name_pattern_mapping

# ============================================================================
# FUNCTION TO GET CATEGORIES FOR A TEMPLATE
# ============================================================================

def get_template_categories(row: pd.Series, id_mapping: Dict, name_pattern_mapping: Dict) -> str:
    """
    Get categories for a template row.
    Checks ID first, then name pattern.
    Returns comma-separated string of categories.
    """
    template_id = row.get('id', '')
    template_name = row.get('name', '')
    
    categories = []
    
    # Check by ID
    if template_id and template_id in id_mapping:
        categories.extend(id_mapping[template_id]["categories"])
    
    # Check by name pattern (exact match or contains)
    if template_name:
        # First try exact match
        if template_name in name_pattern_mapping:
            categories.extend(name_pattern_mapping[template_name])
        else:
            # Try contains match
            for pattern, cats in name_pattern_mapping.items():
                if pattern.lower() in template_name.lower():
                    categories.extend(cats)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_categories = []
    for cat in categories:
        if cat not in seen:
            seen.add(cat)
            unique_categories.append(cat)
    
    if unique_categories:
        return ", ".join(unique_categories)
    
    return "Uncategorized"

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    print("=" * 80)
    print("⚔️  ADDING TEMPLATE CATEGORIES TO GLD TEMPLATES")
    print("=" * 80)
    print(f"📁 JSON Source: {TEMPLATE_JSON_PATH}")
    print(f"📁 Input: {GLD_INPUT_PATH}")
    print(f"📁 Output: {GLD_OUTPUT_PATH}")
    print("=" * 80)
    
    # Load template mapping from JSON
    try:
        print("\n📂 Loading template mapping from JSON...")
        id_mapping, name_pattern_mapping = load_template_mapping(TEMPLATE_JSON_PATH)
        print(f"   ✅ Loaded {len(id_mapping)} template mappings")
        print(f"   ✅ Loaded {len(name_pattern_mapping)} name patterns")
    except Exception as e:
        print(f"❌ Error loading JSON: {e}")
        return
    
    input_file = os.path.join(GLD_INPUT_PATH, "gld_templates.csv")
    
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    
    print(f"\n📂 Reading: {os.path.basename(input_file)}")
    
    try:
        df = pd.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        print(f"   📋 Columns: {list(df.columns)}")
        
        # Check if id column exists
        if 'id' not in df.columns:
            print("   ❌ 'id' column not found!")
            print(f"   📋 Available columns: {list(df.columns)}")
            return
        
        # Check if name column exists (for pattern matching)
        if 'name' not in df.columns:
            print("   ⚠️ 'name' column not found - will only match by ID")
        
        # Apply category mapping
        print("\n⚔️ Applying category mapping...")
        
        # Get categories for each row
        df['template_category'] = df.apply(
            lambda row: get_template_categories(row, id_mapping, name_pattern_mapping), 
            axis=1
        )
        
        # Show summary
        print("\n📊 Category Summary:")
        category_counts = df['template_category'].value_counts()
        for cat, count in category_counts.items():
            print(f"   {cat}: {count} templates")
        
        # Show templates with multiple categories
        multi_cat = df[df['template_category'].str.contains(',', na=False)]
        if not multi_cat.empty:
            print(f"\n📋 Templates with multiple categories ({len(multi_cat)}):")
            for _, row in multi_cat.iterrows():
                print(f"   {row.get('name', 'Unknown')} -> {row['template_category']}")
        
        # Show uncategorized templates
        uncategorized = df[df['template_category'] == 'Uncategorized']
        if not uncategorized.empty:
            print(f"\n⚠️ Uncategorized templates ({len(uncategorized)}):")
            for _, row in uncategorized.head(10).iterrows():
                print(f"   {row.get('id', '')} - {row.get('name', 'Unknown')}")
            if len(uncategorized) > 10:
                print(f"   ... and {len(uncategorized) - 10} more")
        
        # Display the mapping from JSON for reference
        print("\n" + "=" * 80)
        print("📋 TEMPLATE CATEGORY MAPPING (FROM JSON)")
        print("=" * 80)
        
        # Show the mapping grouped by category
        categories_grouped = {}
        for template_id, info in id_mapping.items():
            for cat in info["categories"]:
                if cat not in categories_grouped:
                    categories_grouped[cat] = []
                categories_grouped[cat].append({
                    "id": template_id,
                    "name": info["name"]
                })
        
        for cat, templates in sorted(categories_grouped.items()):
            print(f"\n🏷️  {cat} ({len(templates)} templates):")
            # Only show first 5 to keep output clean
            for t in templates[:5]:
                print(f"      {t['id']} - {t['name']}")
            if len(templates) > 5:
                print(f"      ... and {len(templates) - 5} more")
        
        # Save back to GLD folder
        output_file = os.path.join(GLD_OUTPUT_PATH, "gld_templates.csv")
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n✅ Saved to: {output_file}")
        print(f"   📊 {len(df):,} rows, {len(df.columns)} columns")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()