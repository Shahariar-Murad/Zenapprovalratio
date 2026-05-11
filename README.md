# ZEN Authorization Report Dashboard

Streamlit dashboard for ZEN authorization reports covering Apple Pay, Google Pay, and Card.

## Main logic

- Original ZEN timestamps are treated as GMT+0 / UTC.
- Dashboard converts timestamps to GMT+6 / Bangladesh Time.
- Date filters use the converted GMT+6 date.
- Approval ratio is calculated on unique `merchant_transaction_id` to avoid retry duplication.
- Approved revenue uses `authorization_amount` where `transaction_state = ACCEPTED`.
- Country filter uses full country names instead of short country codes.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload the ZEN Authorization Report CSV from the sidebar.
