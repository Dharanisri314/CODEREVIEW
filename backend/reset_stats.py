# reset_stats.py — run ONCE from your project root
import firebase_admin
from firebase_admin import credentials, firestore as firestore_db

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firebase_admin.firestore.client()

USER_ID = "xKRiEtJyNIRQSkNLR0iOOBJEMGG3"  # ← replace this

sessions     = list(db.collection("codeReviews").document(USER_ID).collection("sessions").stream())
total_issues = sum(s.to_dict().get("issueCount", 0) for s in sessions)

# Count actual code review turns across all session threads
total_reviews = 0
for s in sessions:
    thread = s.to_dict().get("thread", [])
    total_reviews += sum(1 for turn in thread if turn.get("isCodeReview", False))

# totalInteractions: leave as-is (it will now accumulate correctly going forward)
# Just fix totalReviews and totalIssues
db.collection("codeReviews").document(USER_ID).set({
    "totalReviews": total_reviews,
    "totalIssues":  total_issues,
}, merge=True)

print(f"✅ Reset — totalReviews (code only): {total_reviews}, totalIssues: {total_issues}")