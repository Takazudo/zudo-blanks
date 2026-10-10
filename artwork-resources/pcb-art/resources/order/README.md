# Historical Five-Series Quantity Inputs

These imported source-planning CSVs predate the completed four-series order. For the adopted red6+4 quantity-25 set, open [the completed archive](../../../../order-packages/four-art-series/ordered/README.md). These historical inputs are preserved; they are not its purchase list.

The selected wide-Kumiko configuration contains 43 different boards for one five-design set. The draft CSV keeps required quantities separate from supplier order quantities; supplier quantities remain blank until a quote establishes minimum lots, panelization, and extras.

The hardware table lists candidate screw lengths and spacer, nut, and rail-fastener counts. They depend on assumed dimensions and are not purchased part selections. Confirm them against the actual case, nuts, washers, spacers, and assembled stack.

The generator is tools/make_order_plan.py. Its default output is the ignored generated/order-plan directory. Use its --sets and --kumiko options for a revised draft. The script does not replace the imported CSVs or place an order.
