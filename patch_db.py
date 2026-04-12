from backend.database import sync_engine
from backend.models.db_models import Base

def patch_database():
    print("Connecting to database...")
    
    # 1. This deletes ALL existing tables in the database
    Base.metadata.drop_all(bind=sync_engine)
    print("Deleted old tables...")

    # 2. This reads your db_models.py and creates brand new tables with all the correct columns
    Base.metadata.create_all(bind=sync_engine)
    print("✅ Successfully recreated all tables to match your models!")

if __name__ == "__main__":
    patch_database()