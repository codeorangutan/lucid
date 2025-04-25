import os
import configparser

def get_project_root():
    # Returns the project root directory (one level above 'src')
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_config():
    config = configparser.ConfigParser()
    config.read(os.path.join(get_project_root(), 'config.ini'))
    return config

def get_lucid_data_db():
    config = get_config()
    db_path = config['DATABASES']['lucid_data']
    # If not absolute, resolve relative to project root
    if not os.path.isabs(db_path):
        db_path = os.path.join(get_project_root(), db_path)
    return db_path

def get_cns_vs_reports_db():
    config = get_config()
    db_path = config['DATABASES'].get('cns_vs_reports', 'cns_vs_reports.db')
    if not os.path.isabs(db_path):
        db_path = os.path.join(get_project_root(), db_path)
    return db_path
