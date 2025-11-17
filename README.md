# DNSE Lightspeed API Backend

A production-ready FastAPI backend for algorithmic trading via the DNSE Lightspeed API.

## Features

- **Hot-Reload Token Updates**: Update trading tokens without server restart
- **Automatic JWT Authentication**: Auto-login with 8-hour expiration handling
- **Trading Operations**: Place orders, view portfolio
- **Admin Endpoints**: Manage tokens dynamically
- **Full Type Safety**: Strict type hints with Pydantic
- **Async/Await**: High-performance async HTTP client

## Project Structure

```
auto-trading/
├── main.py                 # FastAPI entry point
├── config.py              # Configuration with hot-reload
├── schemas.py             # Pydantic models
├── dnse_client.py         # Async HTTP client
├── routers/
│   ├── admin.py          # Admin endpoints
│   └── trading.py        # Trading endpoints
├── utils/
│   ├── __init__.py
│   └── env_manager.py    # Environment variable manager
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
└── README.md             # This file
```

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd auto-trading
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DNSE_USERNAME=your_username
DNSE_PASSWORD=your_password
DNSE_ACCOUNT_NO=your_account_number
TRADING_TOKEN=your_daily_trading_token
ADMIN_SECRET=your_admin_secret
```

## Running the Server

### Development Mode

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will start at: **http://localhost:8000**

## API Documentation

Once the server is running, access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Trading Operations

#### Place Order

```bash
POST /trading/orders

curl -X POST "http://localhost:8000/trading/orders" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "VNM",
       "side": "NB",
       "orderType": "LO",
       "price": 85.5,
       "quantity": 100
     }'
```

**Parameters:**
- `symbol`: Stock symbol (e.g., "VNM", "HPG")
- `side`: "NB" (buy) or "NS" (sell)
- `orderType`: "LO" (limit), "MP" (market), "ATC", "ATO"
- `price`: Order price
- `quantity`: Number of shares
- `loanPackageId`: (Optional) For margin trading

#### Get Orders

```bash
GET /trading/orders

curl "http://localhost:8000/trading/orders"
```

#### Get Portfolio

```bash
GET /trading/portfolio

curl "http://localhost:8000/trading/portfolio"
```

### Admin Operations

#### Update Trading Token

```bash
POST /admin/update-token

curl -X POST "http://localhost:8000/admin/update-token" \
     -H "X-Admin-Secret: your_admin_secret" \
     -H "Content-Type: application/json" \
     -d '{"new_trading_token": "new_token_value"}'
```

**Security:** Requires `X-Admin-Secret` header.

#### Health Check

```bash
GET /health
GET /admin/health
GET /trading/health
```

## Hot-Reload Token Update

The DNSE trading token changes daily. Update it without restarting:

1. **Via API** (Recommended):
   ```bash
   curl -X POST "http://localhost:8000/admin/update-token" \
        -H "X-Admin-Secret: your_admin_secret" \
        -H "Content-Type: application/json" \
        -d '{"new_trading_token": "new_token_value"}'
   ```

2. **Manual** (requires server restart):
   - Edit `.env` file
   - Restart the server

## Architecture

### Authentication Flow

1. Server starts → Loads config from `.env`
2. First API call → Auto-login to get JWT (valid 8 hours)
3. JWT stored in memory with expiration time
4. Every request checks JWT expiration
5. If expired or 401 error → Auto-relogin

### Hot-Reload Mechanism

1. Admin calls `/admin/update-token`
2. `update_env_file()` → Updates `.env` on disk
3. `reload_settings()` → Clears `@lru_cache`
4. Next request → Fresh config loaded

## Configuration

All settings in `config.py`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DNSE_USERNAME` | DNSE account username | Required |
| `DNSE_PASSWORD` | DNSE account password | Required |
| `DNSE_ACCOUNT_NO` | Trading account number | Required |
| `TRADING_TOKEN` | Daily trading token | Required |
| `ADMIN_SECRET` | Admin API secret | Required |
| `API_BASE_URL` | DNSE API base URL | `https://api.dnse.com.vn` |
| `JWT_EXPIRATION_HOURS` | JWT validity period | `8` |

## Error Handling

- **401 Unauthorized**: Auto-retry with fresh JWT
- **403 Forbidden**: Invalid admin secret
- **500 Internal Server Error**: Request/parsing errors

All errors return JSON:

```json
{
  "error": "Error type",
  "detail": "Detailed error message"
}
```

## Development

### Type Checking

```bash
pip install mypy
mypy .
```

### Code Formatting

```bash
pip install black
black .
```

### Testing

```bash
pip install pytest pytest-asyncio httpx
pytest
```

## Security Considerations

1. **Never commit `.env`** - Use `.env.example` as template
2. **Secure ADMIN_SECRET** - Use strong random string
3. **HTTPS in Production** - Use reverse proxy (nginx)
4. **Rate Limiting** - Consider adding rate limits
5. **Input Validation** - Pydantic handles this automatically

## Troubleshooting

### JWT Expired Errors
- Automatic: Server auto-refreshes JWT
- Manual: Check credentials in `.env`

### Trading Token Invalid
- Update via `/admin/update-token`
- Verify token format from DNSE

### Connection Errors
- Check `API_BASE_URL` in `.env`
- Verify network connectivity
- Check DNSE API status

## License

MIT License

## Support

For issues and questions, please open a GitHub issue.
