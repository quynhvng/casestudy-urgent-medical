import os
import streamlit as st
import numpy as np
import pandas as pd
import benford as bf
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import ticker

plt.rcParams['font.size'] = '8'

@st.cache
def load_data():
  db = dict()
  for file in os.scandir("data"):
    db[file.name.replace(".xlsx", "")] = pd.read_excel(
      file.path,
      parse_dates={"ModifiedDatetime": ["ModifiedDate", "ModifiedTime"]},
      index_col=1)
  # cleaning
  df = db["customer_invoices"]
  df["PaidDate"] = pd.to_datetime(df["PaidDate"], errors="coerce")
  return db

@st.cache
def benford_run(data):
  res = bf.first_digits(
    data, digs=1, decimals=8,
    verbose=False, show_plot=False)
  return res

st.title("Audit Data Analytics Case Study: Urgent Medical Device, Inc.")
"Case by Allen D. Blay (Florida State University), Jay C. Thibodeau (Bentley University), and KPMG."

db = load_data()

st.header("Datasets")
if st.checkbox("View raw data"):
  selected = st.selectbox("Select dataset", db.keys())
  db[selected]

invoices = db["customer_invoices"].query("InvoiceDate.dt.year == 2017")
invoices = invoices[["InvoiceDate", "PaidDate", "SalesOrderID"]]
sales = invoices.join(db["sales_orders"], on="SalesOrderID").set_index("SalesOrderID")
unpaid = sales.query("PaidDate.dt.year != 2017")

"Reconciling data with the supplied trial balance:"
revenue = sales["SubTotal"].sum()
receivable = unpaid["TotalDue"].sum()
f"- Number of valid sales records: {sales.shape[0]:,}. Total sales revenue: ${revenue:,.0f}."
f"- Number of unpaid invoices: {unpaid.shape[0]:,}. Total accounts receivable: ${receivable:,.0f}."
st.markdown("**The datasets were imported completely and accurately.** Invoicing triggers the recording"\
  " of revenue. These numbers are the records the client used to calculate revenue and AR.")

st.header("Substantive testing")

st.subheader("Visualisations of sales data")
def load_viz(selected_viz):
  df = sales[["InvoiceDate", "SubTotal", "TerritoryID"]]
  df = df.join(db["sales_territory"]["TerritoryName"], on="TerritoryID")
  df["QTR"] = df["InvoiceDate"].dt.quarter
  fig, ax = plt.subplots()
  if selected_viz == 0:
    pd.pivot_table(df, index="QTR", values="SubTotal", aggfunc=np.sum)\
      .plot(ax=ax, marker=".", legend=False)
  elif selected_viz == 1:
    pd.pivot_table(df, index="QTR", columns="TerritoryName", values="SubTotal", aggfunc=np.sum)\
      .plot(ax=ax, marker=".")
  elif selected_viz == 2:
    goals = db["sales_territory"][["TerritoryName", "SalesGoalQTR"]]
    goals = goals.sort_values("TerritoryName").reset_index(drop=True)
    pd.pivot_table(df, index="QTR", columns="TerritoryName", values="SubTotal", aggfunc=np.sum)\
      .plot(ax=ax, marker=".", subplots=True, sharex=True, sharey=True, layout=(3, 2))
    for i in goals.index:
      fig.get_axes()[i].axhline(goals.iloc[i,1], ls="--", lw=0.7, c="gray")
  for ax in fig.get_axes():
    ax.set_ylim([0, None])
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    ax.set_xticks([1,2,3,4])
    ax.set_xlabel("Quarter (2017)")
  return fig
viz = [
  "Sales by quarter",
  "Sales by territory by quarter",
  "Sales by territory by quarter vs. 4th quarter sales goal"]
selected_viz = st.selectbox("Select visualisation", viz)
st.write(load_viz(viz.index(selected_viz)))

st.subheader("Three-way matching")
matching = sales[["InvoiceID", "CustID", "TerritoryID", "SubTotal", "ShipID"]]
matching = matching.join(db["shipments"]["ShipDate"], on="ShipID")
matching = matching[matching.isna().any(axis=1)].reset_index()
f"Found {matching.shape[0]} incomplete record(s)."
if matching.shape[0] > 0:
  matching
with st.expander("Process explanation"):
  """Three way matching ensures that all invoices are properly recorded with supporting documents.
  Invoicing triggers revenue recognition. Therefore, I used the invoices as start points to match with
  sales orders (getting <SubTotal>, <ShipID>, …) and then shipment records (getting <ShipDate>). NAs in
  required fields indicate that supporting documents are missing.
  """

st.subheader("Credit limit checking")
checking = unpaid[["CustID", "TotalDue"]].groupby("CustID").sum()
checking = checking.join(db["customer_master"][["CredLimit", "TerritoryID"]], on="CustID").astype(int)
checking = checking.query("TotalDue > CredLimit").reset_index()
f"Found {checking.shape[0]} account(s) exceeding credit limit."
if checking.shape[0] > 0:
  checking
  "The only clear pattern among these customers is that they are in territory ID#5"

st.subheader("Receivables aging analysis")
aging = unpaid.loc[:, ["InvoiceID", "InvoiceDate", "TotalDue"]]
aging["age_days"] = (pd.to_datetime("20171231") - aging["InvoiceDate"]).dt.days
aging = aging.query("age_days > 90").reset_index()
f"Found {aging.shape[0]} invoice(s) exceeding 90 days."
if aging.shape[0] > 0:
  aging

st.subheader("Benford's law analysis")
bf_res = benford_run(sales["SubTotal"])
fig, ax = plt.subplots()
bf_res[["Expected", "Found"]].plot(ax=ax, marker=".", ylabel="Frequency (%)")
ax.set_title("Actual distribution of first digit vs. Expected (Benford's law) distribution")
fig