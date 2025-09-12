def __init__(self, db_path: str = "data/teammates.db"):
    if Database._initialized:
        return

    self.db_path = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    self._init_db()
    self._migrate_data()
    
    if not self._verify_database_integrity():
        logger.error("База данных не прошла проверку целостности")
        
    Database._initialized = True
    logger.info(f"Database инициализирована: {db_path}")