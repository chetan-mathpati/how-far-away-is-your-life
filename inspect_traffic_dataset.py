import pandas as pd

path = r"data\external\bengaluru-traffic-reference\data\Bengaluru_Traffic_Condition_Dataset.xlsx"

excel = pd.ExcelFile(path)

print("SHEETS:")
print(excel.sheet_names)

for sheet in excel.sheet_names:
    df = pd.read_excel(path, sheet_name=sheet)

    print("\n" + "=" * 70)
    print(f"SHEET: {sheet}")
    print("=" * 70)

    print("Shape:", df.shape)
    print("Columns:")
    for column in df.columns:
        print(" -", column)

    print("\nFirst 3 rows:")
    print(df.head(3).to_string(index=False))