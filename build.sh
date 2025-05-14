#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Ejecutando build.sh..."

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar creación de tablas (o migraciones si usas Alembic)
echo "Creando tablas en la base de datos..."
python -c "from database import create_tables; create_tables()"

echo "Build finalizado."