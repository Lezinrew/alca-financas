#!/bin/bash

###############################################################################
# Backup Script - Alça Finanças
# Cria backup do banco de dados e arquivos
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="/var/backups/alcahub"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="alcahub_backup_${TIMESTAMP}"

echo -e "${BLUE}💾 Criando backup do Alça Finanças...${NC}"

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Backup MongoDB
echo "🗄️  Backing up MongoDB..."
docker exec mongodb mongodump --out=/tmp/backup --db=alca_financas
docker cp mongodb:/tmp/backup ${BACKUP_DIR}/${BACKUP_NAME}_mongodb
docker exec mongodb rm -rf /tmp/backup

# Backup uploaded files (if any)
if [ -d "/var/www/alcahub/uploads" ]; then
    echo "📁 Backing up uploaded files..."
    tar -czf ${BACKUP_DIR}/${BACKUP_NAME}_files.tar.gz /var/www/alcahub/uploads
fi

# Compress everything
echo "🗜️  Compressing backup..."
cd ${BACKUP_DIR}
tar -czf ${BACKUP_NAME}.tar.gz ${BACKUP_NAME}_*
rm -rf ${BACKUP_NAME}_*

# Keep only last 7 days
echo "🧹 Cleaning old backups..."
find ${BACKUP_DIR} -name "alcahub_backup_*.tar.gz" -mtime +7 -delete

echo -e "${GREEN}✅ Backup criado: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz${NC}"
