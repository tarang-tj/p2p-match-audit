"""Activity vocabulary and flow types for the BPI Challenge 2019 log.

Names are the exact activity strings in the log. Flow types follow the
challenge description: the Item Category attribute names the matching rule.
"""

CREATE_PO = "Create Purchase Order Item"
GOODS_RECEIPT = "Record Goods Receipt"
CANCEL_GR = "Cancel Goods Receipt"
SERVICE_ENTRY = "Record Service Entry Sheet"
VENDOR_INVOICE = "Vendor creates invoice"
INVOICE_RECEIPT = "Record Invoice Receipt"
CANCEL_IR = "Cancel Invoice Receipt"
SUBSEQUENT_INVOICE = "Record Subsequent Invoice"
CLEAR_INVOICE = "Clear Invoice"
REMOVE_BLOCK = "Remove Payment Block"
SET_BLOCK = "Set Payment Block"
CHANGE_PRICE = "Change Price"
CHANGE_QUANTITY = "Change Quantity"
DELETE_ITEM = "Delete Purchase Order Item"
REACTIVATE_ITEM = "Reactivate Purchase Order Item"

# Item Category values (exact strings) mapped to short flow keys.
FLOW_3WAY_AFTER = "3way_after_gr"
FLOW_3WAY_BEFORE = "3way_before_gr"
FLOW_2WAY = "2way"
FLOW_CONSIGNMENT = "consignment"
FLOW_BY_CATEGORY = {
    "3-way match, invoice after GR": FLOW_3WAY_AFTER,
    "3-way match, invoice before GR": FLOW_3WAY_BEFORE,
    "2-way match": FLOW_2WAY,
    "Consignment": FLOW_CONSIGNMENT,
}
FLOW_LABELS = {
    FLOW_3WAY_AFTER: "3-way, invoice after GR",
    FLOW_3WAY_BEFORE: "3-way, invoice before GR",
    FLOW_2WAY: "2-way",
    FLOW_CONSIGNMENT: "Consignment",
}

# Activities that count as rework on an item: something was entered and then
# corrected, reversed or deleted.
REWORK = (CANCEL_IR, CANCEL_GR, CHANGE_PRICE, CHANGE_QUANTITY, DELETE_ITEM,
          REACTIVATE_ITEM)

NO_USER = "NONE"


def is_batch(user: str) -> bool:
    """Batch users are automated jobs, named batch_NN in the log."""
    return isinstance(user, str) and user.startswith("batch_")


def is_human(user: str) -> bool:
    """Human users are named user_NNN; NONE means no user was recorded."""
    return isinstance(user, str) and user.startswith("user_")
