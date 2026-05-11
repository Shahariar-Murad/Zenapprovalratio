# ZEN Authorization Report Dashboard

This Streamlit dashboard analyzes ZEN authorization data for:

- Apple Pay approval ratio
- Google Pay approval ratio
- Card approval ratio
- Country-wise approved revenue by method
- Country-wise approval ratio
- Decline reason comparison
- Suggested best payment route by country

## Approval Ratio Logic

Approval ratio is calculated using unique `merchant_transaction_id`:

```text
Approval Ratio = Approved Unique Orders / Total Unique Orders × 100
```

An order is considered approved if any transaction attempt under the same `merchant_transaction_id` has `transaction_state = ACCEPTED`.

Revenue is calculated only from accepted transactions using `authorization_amount`.

## Timezone Logic

The original ZEN report timestamp is treated as GMT+0 / UTC. The dashboard converts it to GMT+6 / Bangladesh Time before applying date filters, charts, summaries, raw data display, and CSV export.

Example:

```text
2026-05-09 20:00:00 GMT+0 → 2026-05-10 02:00:00 GMT+6
```

## How to Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then upload the ZEN Authorization Report CSV from the sidebar.

## GitHub + Streamlit Cloud Hosting

1. Create a new GitHub repository.
2. Upload these files:
   - `app.py`
   - `requirements.txt`
   - `README.md`
3. Go to Streamlit Community Cloud.
4. Connect your GitHub repository.
5. Select `app.py` as the main file.
6. Deploy.

## Expected CSV Columns

The app expects these columns:

- `merchant_transaction_id`
- `created_at`
- `transaction_state`
- `authorization_amount`
- `authorization_currency`
- `customer_country`
- `payment_channel`
- `reject_code`
- `transaction_id`

The column names are normalized automatically, so spaces are converted to underscores and uppercase/lowercase differences are handled.
