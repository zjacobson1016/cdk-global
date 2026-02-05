"""
Qualtrics Survey Response Generator

Generates synthetic Qualtrics new product survey responses and writes them
to a Unity Catalog volume for ingestion by the DLT pipeline.

Usage:
    python qualtrics_response_writer.py --profile <databricks_profile> --batches 5 --records-per-batch 10
"""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timedelta

from faker import Faker
from databricks.connect import DatabricksSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Survey configuration
SURVEY_ID = "SV_newprod2026launch"
PRODUCT_NAME = "SmartWidget Pro 3000"

# Choice options for various questions
AWARENESS_SOURCES = [
    ("Email from company", "1"),
    ("Social media", "2"),
    ("Word of mouth", "3"),
    ("Online advertisement", "4"),
    ("Trade show/event", "5"),
    ("News article", "6"),
    ("Company website", "7"),
]

PURCHASE_INTENT_OPTIONS = [
    ("Very unlikely", "1", 1),
    ("Unlikely", "2", 2),
    ("Neutral", "3", 3),
    ("Likely", "4", 4),
    ("Very likely", "5", 5),
]

COMPETITOR_COMPARISON_OPTIONS = [
    ("Much worse", "1", 1),
    ("Worse", "2", 2),
    ("About the same", "3", 3),
    ("Better", "4", 4),
    ("Much better", "5", 5),
]

PURCHASE_TIMELINE_OPTIONS = [
    ("Immediately", "1", 1),
    ("Within 1-3 months", "2", 2),
    ("Within 3-6 months", "3", 3),
    ("Within 6-12 months", "4", 4),
    ("More than a year", "5", 5),
    ("No plans to purchase", "6", 6),
]

CUSTOMER_SEGMENTS = ["Enterprise", "Mid-Market", "Small Business", "Individual"]
CAMPAIGN_SOURCES = ["product_launch_email", "webinar_followup", "trade_show", "partner_referral", "organic"]
DISTRIBUTION_CHANNELS = ["email", "anonymous", "social", "qr", "sms"]

FEATURE_NAMES = ["Performance", "Price", "Ease of use", "Design", "Durability", "Support"]
IMPORTANCE_RATINGS = [
    ("Not Important", 1),
    ("Slightly Important", 2),
    ("Somewhat Important", 3),
    ("Important", 4),
    ("Very Important", 5),
]

OPEN_FEEDBACK_TEMPLATES = [
    "I really like the new design and features. Would love to see more color options.",
    "The product looks promising but I'm concerned about the price point.",
    "Very impressed with the demo. The performance metrics are impressive.",
    "Not sure if this is right for our needs. Would need more customization options.",
    "Great product! Looking forward to the launch.",
    "The features are good but competitors offer better support.",
    "Love the innovation. This could be a game changer for us.",
    "Needs improvement in the user interface. Too complex for beginners.",
    "Excellent value proposition. Will definitely consider purchasing.",
    "The product meets our basic requirements but lacks advanced features.",
]


def generate_response_id() -> str:
    """Generate a Qualtrics-style response ID."""
    return f"R_{uuid.uuid4().hex[:16]}"


def generate_request_id() -> str:
    """Generate a request ID."""
    return f"resp-{uuid.uuid4().hex[:20]}"


def calculate_nps_category(score: int) -> str:
    """Calculate NPS category from score."""
    if score <= 6:
        return "Detractor"
    elif score <= 8:
        return "Passive"
    else:
        return "Promoter"


def calculate_sentiment_score(nps_score: int, purchase_intent_score: int, competitor_score: int) -> float:
    """Calculate overall sentiment score from -1 to 1."""
    # Normalize each component to 0-1 range, then convert to -1 to 1
    nps_normalized = nps_score / 10
    intent_normalized = purchase_intent_score / 5
    competitor_normalized = competitor_score / 5
    
    # Weighted average
    raw_score = (nps_normalized * 0.4 + intent_normalized * 0.35 + competitor_normalized * 0.25)
    # Convert from 0-1 to -1 to 1
    return round((raw_score * 2) - 1, 2)


def calculate_purchase_readiness(purchase_intent_score: int, timeline_score: int, nps_score: int) -> int:
    """Calculate purchase readiness score from 0-100."""
    # Higher intent = higher readiness
    intent_weight = purchase_intent_score * 15  # max 75
    # Shorter timeline = higher readiness (inverse)
    timeline_weight = max(0, (7 - timeline_score) * 5)  # max 30
    # Higher NPS = slight boost
    nps_weight = nps_score  # max 10
    
    return min(100, intent_weight + timeline_weight + nps_weight)


def predict_customer_segment(purchase_readiness: int, nps_category: str) -> str:
    """Predict customer segment based on scores."""
    if purchase_readiness >= 70 and nps_category == "Promoter":
        return "High Value Prospect"
    elif purchase_readiness >= 50:
        return "Interested"
    elif purchase_readiness >= 30:
        return "Curious"
    else:
        return "Not Interested"


def generate_survey_response(fake: Faker, index: int) -> dict:
    """Generate a single synthetic survey response matching the Qualtrics schema."""
    
    # Generate timestamps
    start_time = datetime.utcnow() - timedelta(days=random.randint(1, 30))
    duration_seconds = random.randint(180, 900)  # 3-15 minutes
    end_time = start_time + timedelta(seconds=duration_seconds)
    recorded_time = end_time + timedelta(seconds=random.randint(1, 5))
    
    # Generate survey answers
    awareness_choice = random.choice(AWARENESS_SOURCES)
    purchase_intent_choice = random.choice(PURCHASE_INTENT_OPTIONS)
    nps_score = random.randint(0, 10)
    nps_category = calculate_nps_category(nps_score)
    price_perception = random.randint(20, 95)
    competitor_choice = random.choice(COMPETITOR_COMPARISON_OPTIONS)
    timeline_choice = random.choice(PURCHASE_TIMELINE_OPTIONS)
    consent_given = random.choice([True, False])
    
    # Calculate scores
    sentiment_score = calculate_sentiment_score(nps_score, purchase_intent_choice[2], competitor_choice[2])
    purchase_readiness = calculate_purchase_readiness(purchase_intent_choice[2], timeline_choice[2], nps_score)
    predicted_segment = predict_customer_segment(purchase_readiness, nps_category)
    
    # Generate feature importance responses
    feature_importance_responses = []
    for feature in FEATURE_NAMES:
        rating = random.choice(IMPORTANCE_RATINGS)
        feature_importance_responses.append({
            "featureName": feature,
            "rating": rating[0],
            "ratingRecode": rating[1]
        })
    
    # Generate feature rankings (shuffled order)
    shuffled_features = FEATURE_NAMES.copy()
    random.shuffle(shuffled_features)
    feature_rankings = [
        {"featureName": feature, "rank": rank + 1}
        for rank, feature in enumerate(shuffled_features)
    ]
    
    # Build nested objects as JSON strings to avoid Python dict string representation
    timestamps = json.dumps({
        "startDate": start_time.isoformat() + "Z",
        "endDate": end_time.isoformat() + "Z",
        "recordedDate": recorded_time.isoformat() + "Z",
        "durationSeconds": duration_seconds
    })
    
    respondent = json.dumps({
        "recipientId": f"MLRP_{uuid.uuid4().hex[:12]}",
        "externalDataReference": f"CUST-{fake.random_int(min=10000, max=99999)}",
        "email": fake.email(),
        "firstName": fake.first_name(),
        "lastName": fake.last_name(),
        "ipAddress": fake.ipv4(),
        "userAgent": fake.user_agent()
    })
    
    location_data = json.dumps({
        "latitude": float(fake.latitude()),
        "longitude": float(fake.longitude()),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "country": "United States",
        "postalCode": fake.postcode()
    })
    
    embedded_data = json.dumps({
        "customerSegment": random.choice(CUSTOMER_SEGMENTS),
        "productInterest": PRODUCT_NAME,
        "accountId": f"ACC-{fake.random_int(min=10000, max=99999)}",
        "salesRepId": f"SR-{fake.random_int(min=100, max=999)}",
        "campaignSource": random.choice(CAMPAIGN_SOURCES)
    })
    
    answers = json.dumps({
        "productAwareness": {
            "questionId": "QID1",
            "questionType": "MC",
            "selectedChoice": awareness_choice[0],
            "selectedChoiceId": awareness_choice[1],
            "selectedChoiceRecode": int(awareness_choice[1])
        },
        "purchaseIntent": {
            "questionId": "QID2",
            "questionType": "MC",
            "selectedChoice": purchase_intent_choice[0],
            "selectedChoiceId": purchase_intent_choice[1],
            "selectedChoiceRecode": purchase_intent_choice[2]
        },
        "npsScore": {
            "questionId": "QID3",
            "questionType": "NPS",
            "score": nps_score,
            "npsCategory": nps_category
        },
        "featureImportance": {
            "questionId": "QID4",
            "questionType": "Matrix",
            "responses": feature_importance_responses
        },
        "pricePerception": {
            "questionId": "QID5",
            "questionType": "Slider",
            "value": price_perception
        },
        "competitorComparison": {
            "questionId": "QID6",
            "questionType": "MC",
            "selectedChoice": competitor_choice[0],
            "selectedChoiceId": competitor_choice[1],
            "selectedChoiceRecode": competitor_choice[2]
        },
        "featureRanking": {
            "questionId": "QID7",
            "questionType": "RankOrder",
            "rankings": feature_rankings
        },
        "openFeedback": {
            "questionId": "QID8",
            "questionType": "TE",
            "textResponse": random.choice(OPEN_FEEDBACK_TEMPLATES)
        },
        "purchaseTimeline": {
            "questionId": "QID9",
            "questionType": "MC",
            "selectedChoice": timeline_choice[0],
            "selectedChoiceId": timeline_choice[1],
            "selectedChoiceRecode": timeline_choice[2]
        },
        "followUpConsent": {
            "questionId": "QID10",
            "questionType": "MC",
            "selectedChoice": "Yes" if consent_given else "No",
            "selectedChoiceId": "1" if consent_given else "2",
            "consentGiven": consent_given
        }
    })
    
    scoring = json.dumps({
        "overallSentimentScore": sentiment_score,
        "purchaseReadinessScore": purchase_readiness,
        "customerSegmentPredicted": predicted_segment,
        "npsCategory": nps_category
    })
    
    # Build the complete response object
    # Note: nested objects are JSON strings to ensure proper serialization
    return {
        "meta": json.dumps({
            "requestId": generate_request_id(),
            "httpStatus": "200 - OK"
        }),
        "result": json.dumps({
            "responseId": generate_response_id(),
            "surveyId": SURVEY_ID,
            "responseStatus": random.choice(["Complete", "Complete", "Complete", "Partial"]),  # Mostly complete
            "distributionChannel": random.choice(DISTRIBUTION_CHANNELS),
            "timestamps": json.loads(timestamps),  # Parse back to dict for nested structure
            "respondent": json.loads(respondent),
            "locationData": json.loads(location_data),
            "embeddedData": json.loads(embedded_data),
            "answers": json.loads(answers),
            "scoring": json.loads(scoring)
        })
    }


def write_responses_batch(spark, path: str, start_idx: int, batch_size: int):
    """Write a batch of survey response records to the volume using Spark DataFrame.
    
    Uses Spark's DataFrame write to handle remote /Volumes path via Databricks Connect.
    Writes JSON files that Auto Loader with singleVariantColumn can ingest.
    """
    fake = Faker()
    Faker.seed(start_idx + int(time.time()))
    random.seed(start_idx + int(time.time()))
    
    # Generate response records
    records = [generate_survey_response(fake, start_idx + i) for i in range(batch_size)]
    
    # Create DataFrame from records - Spark infers the schema
    df = spark.createDataFrame(records)
    
    # Write as JSON files
    (
        df.write
        .mode("append")
        .option("compression", "none")
        .json(path)
    )
    
    print(f"Wrote {batch_size} survey response records to {path} at {datetime.utcnow().isoformat()}Z")
    return records


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate Qualtrics survey response data")
    parser.add_argument("--profile", type=str, default="DEFAULT", 
                        help="Databricks CLI profile name")
    parser.add_argument("--catalog", type=str, default="mfg_mc_se_sa",
                        help="Unity Catalog name")
    parser.add_argument("--schema", type=str, default="cdk",
                        help="Schema name")
    parser.add_argument("--volume", type=str, default="survey_responses",
                        help="Volume name")
    parser.add_argument("--batches", type=int, default=1,
                        help="Number of batches to write")
    parser.add_argument("--records-per-batch", type=int, default=10,
                        help="Number of records per batch")
    parser.add_argument("--interval", type=int, default=5,
                        help="Seconds between batches")
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Build volume path
    volume_base = f"/Volumes/{args.catalog}/{args.schema}/{args.volume}"
    responses_path = f"{volume_base}/qualtrics"
    
    print(f"Connecting to Databricks with profile: {args.profile}")
    spark = DatabricksSession.builder.profile(args.profile).serverless().getOrCreate()
    
    print(f"Writing survey responses to: {responses_path}")
    print(f"Batches: {args.batches}, Records per batch: {args.records_per_batch}")
    
    next_idx = 0
    for batch in range(args.batches):
        print(f"\n--- Batch {batch + 1}/{args.batches} ---")
        write_responses_batch(spark, responses_path, next_idx, args.records_per_batch)
        next_idx += args.records_per_batch
        
        if batch < args.batches - 1:
            print(f"Waiting {args.interval} seconds before next batch...")
            time.sleep(args.interval)
    
    print(f"\nCompleted! Wrote {args.batches * args.records_per_batch} total records.")


if __name__ == "__main__":
    main()
