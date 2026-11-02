"""Hindi tenant message templates; parameter order matches the approved English templates."""

HINDI = {
	"Reminder": "नमस्ते {0}, {3} में {2} का आपका किराया {1}, {4} तक देय है। {5}",
	"Due Today": "नमस्ते {0}, {3} में {2} का आपका किराया {1}, {4} तक देय है। {5}",
	"Overdue": "नमस्ते {0}, {3} में {2} का आपका किराया {1}, {4} को देय था और अभी बकाया है। {5}",
	"Receipt": "नमस्ते {0}, {3} में {2} के किराए के लिए {1} प्राप्त हुए। बकाया राशि: {4}। धन्यवाद!",
	"Request Update": 'नमस्ते {0}, आपका अनुरोध "{1}" अब {2} है। {3}',
	"Notice": "नमस्ते {0}, {1} की सूचना: {2}। {3}",
	"Referral": "नमस्ते {0}, {1} ने प्रवेश करके पहला किराया दे दिया है। आपके अगले किराए में {2} की छूट मिलेगी। रेफ़र करने के लिए धन्यवाद!",
	"Deposit": "नमस्ते {0}, आपकी जमा राशि {1} का निपटान हो गया है: {2} {3}। विवरण ऐप में देखें।",
}


def render_hindi(kind, params):
	values = list(params)
	if kind in ("Reminder", "Due Today", "Overdue"):
		values[5] = (
			str(values[5])
			.replace("Pay online:", "ऑनलाइन भुगतान करें:")
			.replace("Pay by UPI to", "UPI से भुगतान करें:")
			.replace("Please pay your landlord.", "कृपया अपने मकान मालिक को भुगतान करें।")
		)
	if kind == "Request Update":
		values[2] = {"open": "खुला", "in progress": "काम जारी", "resolved": "हल किया गया", "closed": "बंद"}.get(
			str(values[2]).lower(), values[2]
		)
		values[3] = str(values[3]).replace("See the tenant app for details.", "विवरण किरायेदार ऐप में देखें।")
	if kind == "Deposit":
		values[3] = {"still to pay": "अभी देय है", "refunded": "वापस किया गया"}.get(values[3], values[3])
	return HINDI[kind].format(*values), values
