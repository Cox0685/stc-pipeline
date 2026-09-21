#!/usr/bin/env python
# coding: utf-8

"""
Add QSET Category to GLD Templates
Reads gld_templates.csv, adds QSET_category column based on mapping
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_PREFIX = "GLD"

client = azure_io.get_client()

# ============================================================================
# QSET CATEGORY MAPPING (template_id -> category)
# ============================================================================

qset_mapping = {
    # --- ENVIRONMENTAL ---
    "79a33e57d78049b4af6cae0b690d4271": "Environmental",
    "01e91f9eb47c4ba29c7d0981bdc72352": "Environmental",
    "80b3094c67174fe3b3ed48a390a6eb68": "Environmental",
    "c4ba5846c87a49f7bf2912e9308caa90": "Environmental",
    "72a7ff23a193418aba3883488f25822e": "Environmental",
    "de6f6dfd804248f4846c6ec5c5f5daf0": "Environmental",
    "cd3084e494a54797a944a068d1a62e65": "Environmental",
    "62f3267d53c943318844576d1e95b8fd": "Environmental",
    "11f4ad9d5c1c4fbb9ab0cc1e74028e69": "Environmental",
    "39c8ef98824747b3a28e02f0802615ba": "Environmental",
    "0cd868bcdd9643b7bfad91cf23078061": "Environmental",
    "7afe7c4558ed434fb884160fce101add": "Environmental",
    "07f683dab0564cba9768fff56508410b": "Environmental",
    "279e0a8081c14069863ddcde84a80c6d": "Environmental",
    "0d8e128dcb344a5a975125ff3bb9a330": "Environmental",
    "021eaeb266f14930ad4ea71a0ed882c0": "Environmental",
    "39eefeec8e0a47e5832f8a57cbd78d7a": "Environmental",
    "f0b386b0798f40a297dfb6eccd7b01db": "Environmental",

    # --- QUALITY ---
    "042ee9caaeb64ec288407ccf3e4b0e63": "Quality",
    "8f6356fbf533424493e81f950a213d4b": "Quality",
    "60a633a987ab42ccb9d184aac2a95905": "Quality",
    "5da8c75c540c40e9ae385e21730b3f57": "Quality",
    "e0b63cb82cfc43fd9efe42b409e0839d": "Quality",
    "94fb37abdad64f148750b526d78a9ba2": "Quality",
    "b5b74fa79a104065b6b080d5ba1d771a": "Quality",
    "9c18b1b4a50f4db7b8683a54392728b9": "Quality",
    "b6b5e7a665104f9294965467e94062c9": "Quality",
    "5fbb11f3eec340e89357a9ea5684ed8d": "Quality",
    "1662e41ec9c041f8a2a40325953f06d9": "Quality",
    "b54da285217d4687b5686943527489cb": "Quality",
    "7dbf5babb97e43fd8b0ada145d1a4ad4": "Quality",
    "98a4291829ca451c9393d3a534cf0e6b": "Quality",
    "fac969c30d184601adbdbc901c567863": "Quality",
    "7c8e71126879425d89aec481cb1b4f99": "Quality",
    "672bfb55c60b496994c533aa795b3887": "Quality",
    "babe7f4e421b4fcf947c32d453563379": "Quality",
    "6370d10b949343f2b30b7e2e991867fa": "Quality",
    "7c369e07d67d45bd852e3aee9913a230": "Quality",
    "5b71ef501ffc4cd6bdc4c199918a50a1": "Quality",
    "5df917fff91c453d94fbe024010785f7": "Quality",
    "9aa4f35181d64bc7a4cc7135717f2b6c": "Quality",
    "5c29bdff23cd48e5a4b829605456f539": "Quality",
    "899768c97dce437ba035269c582c57cb": "Quality",
    "1b85f78a4833420994dfc3f44b2a7318": "Quality",
    "3a0718b204b84823a535dbe3bd3ff4fd": "Quality",

    # --- SAFETY ---
    "0be85c2f65314d6f95a61b1f4692b3bc": "Safety",
    "044a9fc1bf2d481cba2bf38a49bf250e": "Safety",
    "ed1dfdabb88a4354abf41ecd8667ac89": "Safety",
    "f31ca7a8666748888c87c4fb090aa94e": "Safety",
    "5b9f1609c618496a9e98c1c9308e70df": "Safety",
    "7a0e8a6dbc504d35b9ee307c09a0f453": "Safety",
    "a389c01fb0f645d29219f2b56b128895": "Safety",
    "2a2551cf3de24cc09910a6c3acd032ff": "Safety",
    "cafcb1b028314ec59680eb8db530e290": "Safety",
    "4f6681af0a9c462ca211dd815b2c4fa5": "Safety",
    "248eb59fcd1e42648b02e88cc4255b6c": "Safety",
    "b3094798a7e54558a28c972ebb1ed28a": "Safety",
    "70d3a362c5c1435fa299bf05c84b7ec1": "Safety",
    "7cb76de73cf44cd5929604fbbfda5d30": "Safety",
    "ec32742fdac34bfc98de02751d9ffb8a": "Safety",
    "425c380720714e55a4f342cece146da7": "Safety",
    "b84ba425d19e4a2dae2e2da18a00c468": "Safety",
    "5132f8f12f244ba095338bcb9e18985a": "Safety",
    "d94f0f2787444710b1f74883f0c11661": "Safety",
    "38b9d704c88448888cde98f4079285bc": "Safety",
    "288ef0b67f8644e393796941d2e30162": "Safety",
    "80c667b15f724af3935066990952c561": "Safety",
    "de431d663d604745a43a6099a852f3d9": "Safety",
    "b4f93666db7c452781d47fc7494bd4cc": "Safety",
    "c2182b44321142c298a4cfe6125a0f7a": "Safety",
    "2c7ee20e08bb46258ed1dc530d6081ca": "Safety",
    "e916127022364b2e9f3e4c0d86e83940": "Safety",
    "3d08d71d985d4ad285633160eeabaf9f": "Safety",
    "354891b6e0914191bbe4d6fdcb8de9c6": "Safety",
    "26d5870acc7f40d39717539408141037": "Safety",
    "93e52aa935d24b528b62a7bea30c8ede": "Safety",
    "d59caa90dea441f7b2b0948ca3177be3": "Safety",
    "2d029103315f462aa569d1d881c63e44": "Safety",
    "5c3cbb6fa25542778416e61da49996d6": "Safety",
    "19e2a9a5d5ea430fb01ead92991c05ed": "Safety",
    "ac9b61cbbeb341b29514e4217af3d49c": "Safety",
    "bc898dcdf8d54b578d47c2fb4b10efcc": "Safety",
    "c490e843c8524705b6fd0401d1e3d9b7": "Safety",
    "a24d4e2c157242efb7d069d672cd9ddb": "Safety",
    "c37ad5fbdc2f4e9a9c81e3b40c4ca4eb": "Safety",
    "8c907674f4e040ff97484670050347df": "Safety",
    "c5c82f1ca1a34275b453f8b6f06a15cc": "Safety",
    "741e0cb737fb4b0da7f3e2d959b74f04": "Safety",
    "5b62da19e07c456593d3ef8a34e0a46f": "Safety",
    "ca49d490579d4c05a63fd31ba12a8964": "Safety",
    "19c652ff714c411f95294a740b8f5bc1": "Safety",
    "31c895cf0066421f8f0b0d1e6b55fcee": "Safety",
    "3fbe8cd1472f4435b8044f1cc2d5be00": "Safety",
    "ebfd4c472bd9490eb7d3a6ae4d7c26d4": "Safety",
    "3885204c6d734a5aa0d85f9b80eb4a39": "Safety",
    "0e1c501fa799497cbf682ec086cb6cc5": "Safety",
    "353adc779fd04a4ea258291cd4947736": "Safety",
    "be166d7d2e31404b983e661618d1e67f": "Safety",
    "f3d58c8a33cf4e988472acca68104a1b": "Safety",
    "e23145172727499f94dab96466afd052": "Safety",
    "290a2318b45246bc94c4cdf1233023ce": "Safety",
    "90560bc3a134441f9701bedf0fa79e7e": "Safety",
    "11844ac681724a13ae65a65c9832b7e9": "Safety",
    "24b4e63841a94d48948434a019ad4000": "Safety",
    "e0e37e9b93b74e28bb915f9041fec642": "Safety",
    "0e6083324f4941e895af7da95683f43a": "Safety",
    "958a4b2f910749a1afee115251e81ebf": "Safety",
    "cf37552b93ed4328a0ce7b318e1af0d2": "Safety",
    "7f790f2e0495425386aff76e9a88f399": "Safety",
    "a73f30bee4fc4f81af3d252bc2462218": "Safety",
    "5be6969f18b948b48bb15ab5307b52f0": "Safety",
    "77ebcc91a2bc49e3971276d5d4c29794": "Safety",
    "f4db664031644073b59decd29f25b188": "Safety",
    "741af751e3b24d94a3fd548933a6b4b9": "Safety",
    "cb2235cf737945b887a0437641516317": "Safety",
    "18e9a94740f1439da548941ffde82c1c": "Safety",

    # --- ADMIN AND ASSETS ---
    "f2bd1724c8ce4b0f9a6615bc0a75e3ce": "Admin and Assets",
    "a697e870a4264d58a0d28f13a9fe1816": "Admin and Assets",
    "1725395a5c7247f4ac07c4ab7eeecc62": "Admin and Assets",
    "1742c37a420e42c9bdbddec134b7d5bd": "Admin and Assets",
    "dbd57c16f5e40d79f278b60449d19f3": "Admin and Assets",
    "442a203d583f48e287d5018d09e78c34": "Admin and Assets",
    "ad16268cb8c247b3bdad873ac137a7ac": "Admin and Assets",
    "235db8c849434304b1a8b68b572e2bf6": "Admin and Assets",
    "15c738eb51c347e58b3d1e539a3bb43c": "Admin and Assets",

    # --- NON QSET (WIP, Archive, Test, Delete, etc.) ---
    "d291eef8e7584507b19c316536a6a36a": "Non QSET",
    "9dac03f239d24296b4108c7ed313a121": "Non QSET",
    "248b8118f56b4c8fad2a4e1b580ce55f": "Non QSET",
    "4f79bb15e5974e2c8189538578efef39": "Non QSET",
    "50c2825048dd462a9a9f8277a6e9a568": "Non QSET",
    "ae939c6430e346e4bb3e2d8d7102dacd": "Non QSET",
    "bf05298d3639449696d61d03ba7a6a3d": "Non QSET",
    "f852b381831349a9923d7bd528de2062": "Non QSET",
    "0d5798ebe9624472bb2a5509d34e0e7f": "Non QSET",
    "1673e9fe523c48bc8c1cca05ebd59707": "Non QSET",
    "af2652afae754507828a6bb882575bd3": "Non QSET",
    "e5e2816b370546e19c98a206005ce7fd": "Non QSET",
    "4b24c6efd3814bfa84655a2326f8dd8d": "Non QSET",
    "0b0b829d3697481f9147ee57eb410a35": "Non QSET",
    "ce8d98f029fe487c811eb851b9cd64c2": "Non QSET",
    "31e3f7ba1ce143519dd195df78d0ec1d": "Non QSET",
    "c0f5b0c3f9164fc08ee39b84de4affc5": "Non QSET",
    "06b59db92cad49bd82457599a6851474": "Non QSET",
    "1989769a2ec246fab404d327db6b84db": "Non QSET",
    "2248be268783471594a70fe04e40f5df": "Non QSET",
    "374d8f8b12134bef8b03dd43609f57c1": "Non QSET",
    "40635a87e9214b2fb6653246d15ee41a": "Non QSET",
    "5a365d09dd1a4592b66d1a33d49864cf": "Non QSET",
    "713d954ac33542a982758412f4eff330": "Non QSET",
    "84b1e3f60cdb4f76aadf9b62de263e4a": "Non QSET",
    "c2e80b0459b4438b8e2e6f89e652996e": "Non QSET",
    "deaf4a35e88e4ba68b7b62d6030bd05e": "Non QSET",
    "e2bdfa6c869e4c80b33598409b127d9e": "Non QSET",
    "f7e74f7d0c614449a9b9b474ca52d6a4": "Non QSET",
    "3a738c4e397a4039be638a63e4d109a8": "Non QSET",
    "fdd9b1db2254eac9af495fd73b94494": "Non QSET",
    "8cd2426d5a3244cdbc43d64f9f199f2a": "Non QSET",
    "25194f99cd07417fa5663c6e6a870323": "Non QSET",
    "c80173775462487aaa66efed922df8f8": "Non QSET",
    "6ac65ac397d04ee7be033b64b20a69c0": "Non QSET",
    "142be3cf3e9f4f81b35007fe2301f271": "Non QSET",
    "12afc3498e8149f8ae86514c84045b72": "Non QSET",
    "0d3118788b744d4aadece259d991693c": "Non QSET",
    "8017ecb3c1e34ecf812c8413f87a36d6": "Non QSET",
    "dffeda3ef80f4c8eb1be55b80f0851cd": "Non QSET",
    "085d55ea675545679bf66f03cbd62510": "Non QSET",
    "57e2990dd8204e299ae3393aabb3a951": "Non QSET",
    "b80bc9507e414953a8264a67f4bbaefa": "Non QSET",
    "ab6f68c7fbe541b4ad58c8499faf5a35": "Non QSET",
    "a83a9ff09e3740e5992ac4eb11632ac0": "Non QSET",
    "36789d5ce88049a6b2d1d81523eac783": "Non QSET",
    "5dbb82ea3acd4ef9a17076083183edc9": "Non QSET",
    "d0e1f80e6c6d4a859c9f247081c97cb1": "Non QSET",
    "7e8cf2efd60a42068a2ad09453b438aa": "Non QSET",
    "c1d3a3a9e41d463ea695958648d50b11": "Non QSET",
    "975bfadb933d42b18135f8280bd81892": "Non QSET",
    "8cd70c8918a944db92bc0eee9028c96c": "Non QSET",
    "3a506e0a254c466cb0c357df9ce59ffb": "Non QSET",
    "fa854b48c66c410d83a6351cbdd305d1": "Non QSET",
    "35ea63e7ac404025bb921d0918a38a0e": "Non QSET",
    "f1b14c8ccfec44dcac154d9891111b74": "Non QSET",
    "b36206f30b394b2db19345a3af5cc720": "Non QSET",
    "80201cb56e5d42bb9bfeb0da6395878f": "Non QSET",
    "5f3d46bd790749538887bf5d347f3927": "Non QSET",
    "54168833702048ebaf6d2ad9f1bc0385": "Non QSET",
    "6c6334ecee254935b668e626c5ed105f": "Non QSET",
    "a7cc8124cf974eb4a38b228bbbea441f": "Non QSET",
    "d27664ebf562483d9e83210c59ef121b": "Non QSET",
    "7d0bb5eea10c41d99a0dd789dcd6c997": "Non QSET",
    "509bf6bbfa1043a69d2347da5cf62925": "Non QSET",
    "23fcbb61613c4e179433f12c6a34da51": "Non QSET",
    "095d9226b1eb4cbd9ed423eff52fc2e6": "Non QSET",
    "26ce0eaeda3d4636b25e67ec049ba7da": "Non QSET",
    "2e22418ad3ea44fa805e5b9a10462862": "Non QSET",
    "c1dfee2de41e464a923b561856986007": "Non QSET",
    "8ffcf67ce61e4876b89a633fd0a63b15": "Non QSET",
    "6491beff419343cb93c60c152c106fb2": "Non QSET",
    "4ba3400302af4429b1270dc59dbaf6d0": "Non QSET",
    "9748e8d436954f66927ee64ac670b7d8": "Non QSET",
    "9b0cf2cdef1e4a78b196fa98f1e701af": "Non QSET",
}

print("=" * 80)
print("⚔️  ADDING QSET CATEGORY TO GLD TEMPLATES")
print("=" * 80)
print(f"📁 Input: ADLS/{GLD_PREFIX}")
print(f"📁 Output: ADLS/{GLD_PREFIX}")
print("=" * 80)

# ============================================================================
# FUNCTION TO GET QSET CATEGORY FOR A TEMPLATE
# ============================================================================

def get_qset_category(template_id: str) -> str:
    """
    Get QSET category for a template by ID.
    Returns the category or "Uncategorized" if not found.
    """
    if template_id and template_id in qset_mapping:
        return qset_mapping[template_id]
    return "Uncategorized"

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    input_file = f"{GLD_PREFIX}/gld_templates.csv"
    
    if not client.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    
    print(f"\n📂 Reading: {input_file}")
    
    try:
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        print(f"   📋 Columns: {list(df.columns)}")
        
        # Check if id column exists
        if 'id' not in df.columns:
            print("   ❌ 'id' column not found!")
            print(f"   📋 Available columns: {list(df.columns)}")
            return
        
        # Apply QSET category mapping
        print("\n⚔️ Applying QSET category mapping...")
        
        # Get categories for each row
        df['QSET_category'] = df['id'].apply(get_qset_category)
        
        # Show summary
        print("\n📊 QSET Category Summary:")
        category_counts = df['QSET_category'].value_counts()
        for cat, count in category_counts.items():
            print(f"   {cat}: {count} templates")
        
        # Show uncategorized templates (for awareness)
        uncategorized = df[df['QSET_category'] == 'Uncategorized']
        if not uncategorized.empty:
            print(f"\n⚠️ Uncategorized templates ({len(uncategorized)}):")
            for _, row in uncategorized.head(10).iterrows():
                print(f"   {row.get('id', '')} - {row.get('name', 'Unknown')}")
            if len(uncategorized) > 10:
                print(f"   ... and {len(uncategorized) - 10} more")
        
        # Save back to GLD folder
        output_file = f"{GLD_PREFIX}/gld_templates.csv"
        client.write_csv(df, output_file, index=False, encoding='utf-8')
        print(f"\n✅ Saved to: {output_file}")
        print(f"   📊 {len(df):,} rows, {len(df.columns)} columns")
        print(f"   📋 New column: QSET_category")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()