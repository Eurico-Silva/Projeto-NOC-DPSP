from database import init_db, migrate_local_database


def main():
    init_db()
    result = migrate_local_database()
    if result["already_migrated"]:
        print("A migração do banco SQLite já foi executada.")
        return

    imported = result["imported"]
    print("Migração concluída. Linhas importadas por tabela:")
    for table, count in sorted(imported.items()):
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()