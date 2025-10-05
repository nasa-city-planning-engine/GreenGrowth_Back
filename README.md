
# Green Growth - Backend

Welcome to the Green Growth backend!
This backend is built with **Flask**, uses **SQLAlchemy** for database management, and integrates with **Google Earth Engine** for geospatial processing. The environment is ready to run both locally and in Docker containers.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Local Installation](#local-installation)
- [Using Docker](#using-docker)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Useful Commands](#useful-commands)
- [License](#license)

## Features
- RESTful API for managing users, messages, and geoprocessing.
- Integration with Google Earth Engine.
- SQLite database (development) and support for PostgreSQL (production).
- Docker containers ready for deployment.
- CORS enabled to facilitate frontend-backend development.

## Prerequisites
- [Python 3.11+](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/)
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) (optional, recommended for production)
- Google Cloud credentials (JSON file)

## Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/nasa-city-planning-engine/backend.git
   cd backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On Mac/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   - Copy the `.flaskenv.template` file to `.flaskenv` and fill in the required values.
   - Make sure you have the Google credentials file at the indicated path.

5. **Initialize the database:**
   ```bash
   flask --app app.py init-db
   ```

6. **Run the server:**
   ```bash
   flask run
   ```
   The backend will be available at [http://localhost:5000](http://localhost:5000)

## Using Docker

1. **Copy your Google credentials to the `secrets/` folder**
   - Example: `secrets/greengrowth-474117-1b31077e1243.json`

2. **Build and start the containers:**
   ```bash
   docker-compose up --build
   ```
   The backend will be available at [http://localhost:5001](http://localhost:5001)

## Environment Variables

- **DB_URL**: Database URL (default is SQLite for development)
- **GEE_PROJECT**: Google Earth Engine project ID
- **GOOGLE_APPLICATION_CREDENTIALS**: Path to the Google credentials file
- **FLASK_APP**: Main Flask app file
- **FLASK_ENV**: Flask environment (`development` or `production`)

You can see an example in `.flaskenv.template`.

## Project Structure

```
backend/
├── app.py                # Main entry point
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker image
├── docker-compose.yml    # Container orchestration
├── .flaskenv.template    # Environment variable template
├── models/               # Database models
├── routers/              # API blueprints and routes
├── utils/                # Utilities and helper logic
├── secrets/              # Credentials (do not commit to git)
└── instance/             # Database files (created at runtime)
```

## Useful Commands

- **Initialize the database:**
  ```bash
  flask --app app.py init-db
  ```
- **Start the Flask server:**
  ```bash
  flask run
  ```
- **Start with Docker Compose:**
  ```bash
  docker-compose up --build
  ```

## License

This project is part of the NASA Space Apps Challenge 2025 hackathon.
