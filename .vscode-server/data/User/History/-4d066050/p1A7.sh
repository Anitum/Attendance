#!/bin/bash
recipient="$1"
subject="$2"
message="$3"

curl -s --user "api:YOUR_API_KEY" \
    https://api.mailgun.net/v3/your-domain.com/messages \
    -F from="Your Name <your@email.com>" \
    -F to="$recipient" \
    -F subject="$subject" \
    -F text="$message"