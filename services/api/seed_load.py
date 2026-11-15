"""Generate realistic load test data for benchmarking API endpoints.

Usage:
    python -m services.api.seed_load [--output-dir DIR] [--incidents N] [--ingredients N] [--movements N] [--suppliers N]

Creates TinyDB and SQLite databases with realistic, varied data suitable for
performance testing. All data is written to temporary files, never to production data.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import os
import random
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB
from tinydb.table import Table

from .database import get_suppliers_table, get_incidents_tables
from .inventory.database import init_inventory_db
from .inventory.models import Ingredient, IngredientEntry, IngredientExit
from .models import Supplier, UserCreate, UserRole
from .services_auth import crear_usuario, crear_perfil
from .models import ProfileCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants from the actual model
BRANCHES = ("central", "norte", "oriente", "occidente", "sur", "suroeste", "suroriente", "nororiente")
CATEGORIES = ("supply_issue", "delivery_delay", "quality_concern", "compliance", "other")
STATUSES = ("open", "in_progress", "resolved", "closed", "discarded")
ORIGINS = ("customer", "employee", "system")
INGREDIENT_CATEGORIES = ("meat", "produce", "sauce", "beverage", "packaging", "cleaning")
SUPPLIER_CATEGORIES = ("carne", "verduras_y_hortalizas", "salsas_y_condimentos", "bebidas", "packaging", "productos_limpieza", "lacteos", "carbon_y_combustible")
LOCATION_IDS = list(range(1, 15))  # 1-14 for location_id constraint
SUPPLIER_COUNTRIES = ("Colombia", "USA")


def generate_incidents(db_path: Path, count: int = 1000) -> int:
    """Generate realistic incident records with varied categories, statuses, branches and dates."""
    logger.info(f"Generating {count} incidents...")
    
    created = 0
    with TinyDB(str(db_path)) as db:
        incidents_table = db.table("incidents")
        seed_keys_table = db.table("incident_seed_keys")
        
        base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        
        for i in range(count):
            # Vary dates over the past 6 months
            days_offset = random.randint(0, 180)
            date = base_date + timedelta(days=days_offset, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            # Realistic text that changes
            category = random.choice(CATEGORIES)
            branch = random.choice(BRANCHES)
            
            incident_id = f"INC-{i+1:06d}"
            record = {
                "title": f"Incident {category} at {branch} - {date.strftime('%Y-%m-%d')}",
                "description": f"Detailed incident description for {incident_id}. "
                              f"Category: {category}. Branch: {branch}. "
                              f"Details about the issue: {random.choice(['supply short', 'delivery missed', 'quality defect', 'compliance risk', 'system error'])}",
                "category": category,
                "status": random.choice(STATUSES),
                "origin": random.choice(ORIGINS),
                "branch": branch,
                "created_at": date.isoformat(),
                "updated_at": (date + timedelta(hours=random.randint(0, 48))).isoformat(),
            }
            
            doc_id = incidents_table.insert(record)
            seed_keys_table.insert({"incident_id": incident_id, "doc_id": doc_id})
            created += 1
            
            if (i + 1) % 100 == 0:
                logger.info(f"  Created {i + 1}/{count} incidents")
    
    logger.info(f"Total incidents created: {created}")
    return created


def generate_suppliers(db_path: Path, count: int = 100) -> int:
    """Generate realistic supplier records with varied categories and countries."""
    logger.info(f"Generating {count} suppliers...")
    
    created = 0
    
    with TinyDB(str(db_path)) as db:
        suppliers_table = db.table("suppliers")
        
        for i in range(count):
            record = {
                "name": f"Supplier {i+1:04d} - {random.choice(['Premium', 'Standard', 'Bulk', 'Express', 'Eco'])}",
                "country": random.choice(SUPPLIER_COUNTRIES),
                "categories": random.sample(SUPPLIER_CATEGORIES, random.randint(1, 3)),
                "rate_per_unit": random.uniform(1000, 50000),
                "currency": random.choice(["COP", "USD"]),
                "status": random.choice(["active", "suspended"]),
                "contact_email": f"supplier{i+1:04d}@example.com",
                "notes": f"Generated supplier {i+1} for load testing. Reliability: {random.choice(['high', 'medium', 'variable'])}",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            suppliers_table.insert(record)
            created += 1
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Created {i + 1}/{count} suppliers")
    
    logger.info(f"Total suppliers created: {created}")
    return created


def generate_inventory(db_url: str, ingredients: int = 200, movements: int = 10000) -> tuple[int, int, int]:
    """Generate realistic ingredient and movement records with coherent stock levels."""
    logger.info(f"Generating {ingredients} ingredients with {movements} total movements...")
    
    engine = create_engine(db_url, echo=False)
    SQLModel.metadata.create_all(engine)
    
    created_ingredients = 0
    created_entries = 0
    created_exits = 0
    
    with Session(engine) as session:
        # Create ingredients
        ingredient_ids = []
        for i in range(ingredients):
            ingredient = Ingredient(
                name=f"Ingredient {i+1:04d} - {random.choice(['premium', 'standard', 'bulk'])} grade",
                sku=f"SKU-{i+1:06d}",
                unit=random.choice(["kg", "litro", "unidad"]),
                category=random.choice(INGREDIENT_CATEGORIES),
                country=random.choice(["CO", "US"]),
            )
            session.add(ingredient)
            created_ingredients += 1
            
            if (i + 1) % 20 == 0:
                logger.info(f"  Created {i + 1}/{ingredients} ingredients")
        
        session.commit()
        
        # Get all created ingredients
        from sqlmodel import select
        ingredient_ids = [ing.id for ing in session.exec(select(Ingredient)).all()]
        logger.info(f"Total ingredients created: {created_ingredients}")
    
    # Create movements with coherent stock
    movements_per_ingredient = movements // max(1, len(ingredient_ids))
    base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    
    with Session(engine) as session:
        stock_by_location: dict[int, dict[int, float]] = {ing_id: {} for ing_id in ingredient_ids}
        
        for ing_idx, ingredient_id in enumerate(ingredient_ids):
            movements_for_this = movements_per_ingredient
            if ing_idx == len(ingredient_ids) - 1:
                movements_for_this = movements - (created_entries + created_exits)
            
            # First entries, then exits
            entries_count = movements_for_this // 2
            exits_count = movements_for_this - entries_count
            
            # Generate entries first
            for m in range(entries_count):
                days_offset = random.randint(0, 180)
                date = base_date + timedelta(days=days_offset, hours=random.randint(0, 23))
                quantity = random.uniform(10, 500)
                location_id = random.choice(LOCATION_IDS)
                
                entry = IngredientEntry(
                    ingredient_id=ingredient_id,
                    quantity=quantity,
                    supplier_name=f"Supplier-{random.randint(1, 50):03d}",
                    location_id=location_id,
                    created_at=date,
                    user_uuid="test-user-uuid",
                )
                session.add(entry)
                created_entries += 1
                
                if location_id not in stock_by_location[ingredient_id]:
                    stock_by_location[ingredient_id][location_id] = 0
                stock_by_location[ingredient_id][location_id] += quantity
            
            # Generate exits (respecting available stock)
            for m in range(exits_count):
                days_offset = random.randint(0, 180)
                date = base_date + timedelta(days=days_offset, hours=random.randint(0, 23))
                location_id = random.choice(LOCATION_IDS)
                
                available = stock_by_location[ingredient_id].get(location_id, 0)
                if available > 0:
                    max_qty = min(available * 0.95, 200)  # Don't deplete completely
                    quantity = random.uniform(1, max_qty)
                    
                    exit_record = IngredientExit(
                        ingredient_id=ingredient_id,
                        quantity=quantity,
                        reason=random.choice(["consumption", "waste"]),
                        location_id=location_id,
                        created_at=date,
                        user_uuid="test-user-uuid",
                    )
                    session.add(exit_record)
                    created_exits += 1
                    stock_by_location[ingredient_id][location_id] -= quantity
            
            if (ing_idx + 1) % 20 == 0:
                logger.info(f"  Created movements for {ing_idx + 1}/{len(ingredient_ids)} ingredients")
        
        session.commit()
    
    engine.dispose()
    logger.info(f"Total entries created: {created_entries}")
    logger.info(f"Total exits created: {created_exits}")
    
    return created_ingredients, created_entries, created_exits


def create_test_user(auth_db_path: Path) -> tuple[str, str]:
    """Create a test user in the auth database for protected endpoint testing."""
    logger.info("Creating test user...")
    
    # We need to mock the database path to use our temp one
    import services.api.services_auth as auth_module
    original_path = auth_module.AUTH_DATABASE_PATH
    auth_module.AUTH_DATABASE_PATH = auth_db_path
    
    try:
        email = "benchmark-test@example.com"
        password = "TestPassword123!"
        
        user = crear_usuario(UserCreate(email=email, password=password, role=UserRole.user))
        logger.info(f"Test user created: {email}")
        
        return email, password
    finally:
        auth_module.AUTH_DATABASE_PATH = original_path


def main():
    """Generate load test data in temporary location."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate load test data")
    parser.add_argument("--output-dir", type=str, help="Output directory for test data")
    parser.add_argument("--incidents", type=int, default=1000, help="Number of incidents to generate")
    parser.add_argument("--ingredients", type=int, default=200, help="Number of ingredients")
    parser.add_argument("--movements", type=int, default=10000, help="Total inventory movements")
    parser.add_argument("--suppliers", type=int, default=100, help="Number of suppliers")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir) if args.output_dir else Path("services/api/.loadtest")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Paths for test databases
        incidents_path = output_dir / "incidents.json"
        suppliers_path = output_dir / "suppliers.json"
        auth_path = output_dir / "auth.json"
        inventory_db_url = f"sqlite:///{output_dir / 'inventory.db'}"
        
        # Clean up any existing test data
        for path in [incidents_path, suppliers_path, auth_path, output_dir / "inventory.db"]:
            if path.exists():
                path.unlink()
        
        # Generate data
        incidents_count = generate_incidents(incidents_path, args.incidents)
        suppliers_count = generate_suppliers(suppliers_path, args.suppliers)
        
        os.environ["DATABASE_URL"] = inventory_db_url
        ingredients_count, entries_count, exits_count = generate_inventory(inventory_db_url, args.ingredients, args.movements)
        
        # Create test user
        email, password = create_test_user(auth_path)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("LOAD TEST DATA GENERATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Incidents: {incidents_count}")
        logger.info(f"Suppliers: {suppliers_count}")
        logger.info(f"Ingredients: {ingredients_count}")
        logger.info(f"Inventory entries: {entries_count}")
        logger.info(f"Inventory exits: {exits_count}")
        logger.info(f"Test user email: {email}")
        logger.info(f"Test user password: {password}")
        logger.info(f"Inventory DB URL: {inventory_db_url}")
        logger.info("="*60 + "\n")
        
        return 0
    
    except Exception as exc:
        logger.error(f"Error generating load test data: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
