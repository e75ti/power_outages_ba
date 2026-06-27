# Electricity Outage Scraper

This project is a web scraper designed to collect information on electricity outages from specified websites. It allows users to subscribe for notifications based on street names and utilizes geographical checks to ensure accurate notifications.

## Project Structure

```
electricity-outage-scraper
├── src
│   ├── main.py                  # Entry point of the application
│   ├── scrapers
│   │   ├── __init__.py
│   │   └── outage_scraper.py    # Scraper for collecting outage information
│   ├── services
│   │   ├── __init__.py
│   │   ├── notification_service.py # Handles user notifications
│   │   ├── subscription_service.py # Manages user subscriptions
│   │   └── geo_service.py        # Performs geographical checks
│   ├── models
│   │   ├── __init__.py
│   │   ├── outage.py             # Represents an electricity outage event
│   │   └── subscription.py        # Represents a user subscription
│   ├── database
│   │   ├── __init__.py
│   │   └── db_manager.py         # Manages database interactions
│   ├── utils
│   │   ├── __init__.py
│   │   └── config.py             # Configuration settings
│   └── config
│       └── settings.py           # Application settings
├── tests
│   ├── __init__.py
│   ├── test_scrapers.py          # Unit tests for the outage scraper
│   ├── test_services.py          # Unit tests for service classes
│   └── test_models.py            # Unit tests for data models
├── requirements.txt              # Project dependencies
├── .env.example                   # Example environment variables
└── README.md                     # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd electricity-outage-scraper
   ```

2. **Create a virtual environment:**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Copy `.env.example` to `.env` and fill in the required values.

## Usage

To run the application, execute the following command:
```
python src/main.py
```

## Notification Services

The application integrates with various notification services to alert users about outages. Ensure to configure the necessary API keys in the `.env` file.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.