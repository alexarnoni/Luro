# Luro - Personal Finance Manager

Luro is a modern personal finance management web application built with FastAPI, featuring magic link authentication, account tracking, transaction management, and financial goal setting.

## Features

- 🔐 **Magic Link Authentication** - Passwordless login via email using Resend
- 💰 **Account Management** - Track multiple financial accounts (checking, savings, credit, etc.)
- 📊 **Transaction Tracking** - Manual entry and categorization of income and expenses
- 🎯 **Financial Goals** - Set and track progress towards savings goals
- 📈 **Insights** - Get insights into your financial habits
- 🎨 **Modern UI** - Clean, responsive interface built with Jinja2 templates

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite with SQLAlchemy (async) + Alembic migrations
- **Frontend**: Jinja2 templates, vanilla CSS
- **Authentication**: Magic link via Resend API
- **Deployment**: Docker + docker-compose

## Project Structure

```
Luro/
├── app/
│   ├── core/              # Core configurations and database
│   │   ├── config.py      # Application settings
│   │   ├── database.py    # Database setup
│   │   └── security.py    # Magic link management
│   ├── domain/            # Domain models
│   │   ├── users/         # User models
│   │   ├── accounts/      # Account models
│   │   ├── transactions/  # Transaction models
│   │   ├── goals/         # Goal models
│   │   └── insights/      # Insight models
│   └── web/               # Web layer
│       ├── routes/        # Route handlers
│       ├── templates/     # Jinja2 templates
│       └── static/        # CSS, JS, images
├── alembic/               # Database migrations
├── main.py                # Application entry point
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
└── docker-compose.yml    # Docker Compose setup
```

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/alexarnoni/Luro.git
cd Luro
```

2. Create a `.env` file (optional, for production):
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Run with docker-compose:
```bash
docker-compose up
```

4. Open your browser to `http://localhost:8000`

### Manual Setup

1. Clone the repository:
```bash
git clone https://github.com/alexarnoni/Luro.git
cd Luro
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run the application:
```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn main:app --reload
```

6. Open your browser to `http://localhost:8000`

## Configuration

Key environment variables (see `.env.example`):

- `DATABASE_URL`: Database connection string (default: SQLite)
- `SECRET_KEY`: Secret key for session management
- `RESEND_API_KEY`: API key for Resend email service
- `RESEND_FROM_EMAIL`: Email address to send magic links from
- `DEBUG`: Enable debug mode (shows magic links in browser for development)

## Usage

1. **Login**: Navigate to `/login` and enter your email. In debug mode, the magic link will be displayed on the page. In production, it will be sent via email.

2. **Dashboard**: After logging in, view your financial overview including total balance, accounts, and recent transactions.

3. **Accounts**: Create and manage multiple financial accounts (checking, savings, credit cards, etc.).

4. **Transactions**: Add income and expenses manually, categorize them, and track your spending.

5. **Goals**: Set financial goals with target amounts and dates, track your progress.

## Database Migrations

The application uses Alembic for database migrations. To create a new migration:

```bash
# Copy the example alembic.ini
cp alembic.ini.example alembic.ini

# Create a migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```

## Development

The application is structured in layers:

- **Core Layer**: Configuration, database, security
- **Domain Layer**: Business entities (users, accounts, transactions, goals, insights)
- **Web Layer**: HTTP routes, templates, static files

To add new features:

1. Create models in the appropriate `app/domain/` directory
2. Add routes in `app/web/routes/`
3. Create templates in `app/web/templates/`
4. Update styles in `app/web/static/css/`

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
