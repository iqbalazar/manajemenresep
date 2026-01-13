# utils.py
import pandas as pd
from io import BytesIO

def normalize_units(df):
    rules = {
        'kg': ('gram', 1000), 'kilo': ('gram', 1000), 'liter': ('ml', 1000), 
        'l': ('ml', 1000), 'ons': ('gram', 100)
    }
    def convert(row):
        u = str(row['unit']).lower().strip()
        q = row['total_quantity']
        if u in rules:
            new_u, factor = rules[u]
            return pd.Series([q * factor, new_u])
        return pd.Series([q, row['unit']])
    
    if not df.empty:
        df[['total_quantity', 'unit']] = df.apply(convert, axis=1)
    return df

def format_indo(num):
    s = f"{num:,.2f}".translate(str.maketrans({',': '.', '.': ','}))
    if ',' in s: s = s.rstrip('0').rstrip(',')
    return s

def format_output(val, unit):
    final_val = val
    final_unit = unit
    if unit == 'gram' and val >= 1000: final_val /= 1000; final_unit = 'kg'
    elif unit == 'ml' and val >= 1000: final_val /= 1000; final_unit = 'liter'
    return f"{format_indo(final_val)} {final_unit}"

def generate_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    save_df = df[['ingredient_name', 'Estimasi Belanja']].rename(columns={'Estimasi Belanja': 'Harus Dibeli'})
    save_df.to_excel(writer, index=False, sheet_name='Belanja')
    
    wb = writer.book; ws = writer.sheets['Belanja']
    fmt_Head = wb.add_format({'bold': True, 'fg_color': '#4CAF50', 'font_color': 'white', 'border': 1})
    fmt_Body = wb.add_format({'border': 1})
    
    for c, val in enumerate(save_df.columns): ws.write(0, c, val, fmt_Head)
    ws.set_column('A:A', 30, fmt_Body); ws.set_column('B:B', 20, fmt_Body)
    
    writer.close()
    return output.getvalue()
