# Email Alerts Setup Guide

## Quick Start

### 1. Get Gmail App Password

1. Go to your Google Account: https://myaccount.google.com/
2. Select **Security**
3. Under "Signing in to Google," select **2-Step Verification** (enable if not already)
4. At the bottom, select **App passwords**
5. Select app: **Mail**
6. Select device: **Other (Custom name)** → enter "100AC Trading System"
7. Click **Generate**
8. **Copy the 16-character password** (you'll use this in step 2)

### 2. Configure Email Settings

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   # Email Alert Configuration
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-actual-email@gmail.com
   SMTP_PASSWORD=your-16-char-app-password
   FROM_EMAIL=your-actual-email@gmail.com
   TO_EMAIL=krsna.nandula@gmail.com
   EMAIL_ALERTS_ENABLED=true
   ```

### 3. Test Email Alerts

Run the analysis script:
```bash
python scripts/analyze_gold_silver.py
```

You should receive an email for any signal with:
- **Confidence ≥ 70** (strong BUY signals)
- **Confidence ≤ 30** (strong SELL signals)

## Email Format

You'll receive HTML-formatted emails with:
- 🟢 **Symbol and Action** (color-coded: green for BUY, red for SELL)
- 📊 **Confidence Score** (0-100)
- 📈 **Technical Score** (0-50)
- 🌍 **Macro Score** (0-50)
- 💰 **Position Size** recommendation
- 🎯 **Entry Price, Stop Loss, Target**
- ⚖️ **Risk/Reward Ratio**
- 🕐 **Timestamp**

## Troubleshooting

### "SMTP credentials not configured"
- Make sure you've created the `.env` file (not just `.env.example`)
- Check that `SMTP_USER` and `SMTP_PASSWORD` are filled in

### "Authentication failed"
- Verify you're using an **App Password**, not your regular Gmail password
- Make sure 2-Step Verification is enabled on your Google account
- Check for typos in your email/password

### "Email alerts are disabled"
- Set `EMAIL_ALERTS_ENABLED=true` in your `.env` file

### No emails received
- Check your spam folder
- Verify `TO_EMAIL` is correct in `.env`
- Make sure signals have confidence ≥ 70 or ≤ 30
- Check the terminal output for error messages

## Using Other Email Providers

### Outlook/Hotmail
```bash
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password
```

### Yahoo Mail
```bash
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
```

### Custom SMTP Server
```bash
SMTP_SERVER=mail.yourcompany.com
SMTP_PORT=587  # or 465 for SSL
SMTP_USER=your-username
SMTP_PASSWORD=your-password
```

## Customizing Alert Thresholds

Edit [scripts/analyze_gold_silver.py](../scripts/analyze_gold_silver.py) line ~155:

```python
# Current: Send email for confidence >= 70 or <= 30
if confidence >= 70 or confidence <= 30:

# Example: Send for ALL signals
if True:

# Example: Only very strong signals
if confidence >= 85 or confidence <= 15:
```

## Security Notes

⚠️ **Never commit your `.env` file to git!**

The `.env` file is already in `.gitignore`, but be careful:
- Don't share your App Password
- Don't include credentials in screenshots
- Rotate your App Password if compromised

## Disabling Email Alerts

To disable email alerts temporarily:

```bash
# In .env file:
EMAIL_ALERTS_ENABLED=false
```

Or remove the email sending code from `analyze_gold_silver.py`.
