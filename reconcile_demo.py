"""
Bill reconciliation demo (synthetic data).

Shows the method used in the private audit work:
  1. Recalculate every bill line from quantity x rate.
  2. Compare with the amount printed on the bill.
  3. Check that the printed lines add up to the printed total.
  4. Explain the change between two months as a waterfall.

The numbers in sample_data/ are invented for illustration. No client data.
Run:  python reconcile_demo.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TOLERANCE_RS = 1.0  # differences up to Rs 1 are rounding

bills = pd.read_csv("sample_data/synthetic_bills.csv")
results = []

for month, bill in bills.groupby("month", sort=True):
    lines = bill[bill.line_item != "PRINTED TOTAL PAYABLE"].copy()
    printed_total = bill.loc[bill.line_item == "PRINTED TOTAL PAYABLE", "printed_amount_rs"].iloc[0]

    # Step 1-2: recalculate lines that have a quantity and a rate
    has_rate = lines.basis_qty.notna() & lines.rate_rs.notna()
    lines.loc[has_rate, "recalculated_rs"] = (lines.basis_qty * lines.rate_rs).round(0)

    # Electricity duty is a percentage of the charges above it
    duty = lines.line_item == "Electricity duty"
    charges_before_duty = lines.loc[has_rate, "recalculated_rs"].sum()
    lines.loc[duty, "recalculated_rs"] = round(charges_before_duty * lines.loc[duty, "rate_rs"].iloc[0] / 100, 0)

    # The solar credit comes from a separate settlement sheet; take it as printed
    credit = lines.line_item == "Solar open-access credit"
    lines.loc[credit, "recalculated_rs"] = lines.loc[credit, "printed_amount_rs"]

    lines["difference_rs"] = lines.printed_amount_rs - lines.recalculated_rs
    lines["status"] = lines.difference_rs.abs().map(lambda d: "MATCH" if d <= TOLERANCE_RS else "CHECK")

    # Step 3: do the printed lines add up to the printed total?
    sum_of_lines = lines.printed_amount_rs.sum()
    total_ok = abs(sum_of_lines - printed_total) < TOLERANCE_RS

    print(f"\n=== {month} ===")
    print(lines[["line_item", "printed_amount_rs", "recalculated_rs", "difference_rs", "status"]].to_string(index=False))
    print(f"Sum of lines Rs {sum_of_lines:,.0f} vs printed total Rs {printed_total:,.0f} -> "
          f"{'RECONCILED' if total_ok else 'DOES NOT ADD UP'}")
    results.append(lines.assign(month=month))

all_lines = pd.concat(results)
all_lines.to_csv("reconciliation_output.csv", index=False)

# Step 4: why did the bill change? (waterfall Jan -> Feb)
pivot = all_lines.pivot_table(index="line_item", columns="month", values="printed_amount_rs", aggfunc="sum")
m1, m2 = pivot.columns[:2]
change = (pivot[m2] - pivot[m1]).sort_values(key=abs, ascending=False)
start, end = pivot[m1].sum(), pivot[m2].sum()

labels = [f"{m1} bill"] + list(change.index) + [f"{m2} bill"]
values = [start] + list(change.values) + [end]
fig, ax = plt.subplots(figsize=(11, 4.5))
running = start
for i, (lab, v) in enumerate(zip(labels, values)):
    if i == 0 or i == len(labels) - 1:
        ax.bar(i, v / 1e5, color="#1f6f8b")
        ax.text(i, v / 1e5 + .1, f"{v/1e5:.2f}", ha="center", fontsize=9)
    else:
        bottom = running if v >= 0 else running + v
        ax.bar(i, abs(v) / 1e5, bottom=bottom / 1e5, color="#d1495b" if v > 0 else "#2a9d8f")
        ax.text(i, (bottom + abs(v)) / 1e5 + .1, f"{v/1e5:+.2f}", ha="center", fontsize=9)
        running += v
ax.set_xticks(range(len(labels)))
SHORT = {"Fuel & power purchase adjustment": "Fuel\nadjustment", "Time-of-use charge (peak hours)": "Peak-hour\ncharge",
         "Solar open-access credit": "Solar\ncredit", "Power factor rebate": "PF\nrebate", "Electricity duty": "Electricity\nduty"}
ax.set_xticklabels([SHORT.get(l, l.replace(" ", "\n", 1)) for l in labels], fontsize=8)
ax.set_ylabel("Rs lakh"); ax.set_title("Why did the bill change? (synthetic example; red = cost up, green = cost down)")
ax.grid(axis="y", alpha=.3); fig.tight_layout(); fig.savefig("charts/bill_change_waterfall.png", dpi=150)
print(f"\nBill moved from Rs {start:,.0f} to Rs {end:,.0f}; biggest driver: {change.index[0]} ({change.iloc[0]:+,.0f})")
