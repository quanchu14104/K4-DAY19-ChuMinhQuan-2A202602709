import os
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase

uri = "neo4j://localhost:7687"
user = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password123")

driver = GraphDatabase.driver(uri, auth=(user, password))

print("=== LỖI E1: Cầu nối gãy ===")
with driver.session() as session:
    res = session.run("MATCH (k:Case) WHERE NOT (k)-[:CHARGED_WITH]->() RETURN k.name, k.doc_id")
    for record in res:
        print(record.data())

print("\n=== LỖI E2: Thiếu ngữ cảnh luật ===")
with driver.session() as session:
    res = session.run("MATCH (k:Case)-[:INVOLVES]->(s) WHERE k.name CONTAINS 'Hoàng Nato' RETURN k.name, s.name")
    data = [record.data() for record in res]
    print("Hoang Nato case involves:", data)
    if not data:
        # try without Hoang Nato
        res2 = session.run("MATCH (k:Case) WHERE toLower(k.name) CONTAINS 'hoàng nato' OR k.name CONTAINS 'Dương Minh Tuấn' RETURN k.name")
        print("Cases:", [r.data() for r in res2])
        
    res3 = session.run("MATCH (k:Case)-[:INVOLVES]->(s) WHERE k.name CONTAINS 'Tuấn' RETURN k.name, s.name LIMIT 5")
    print("Other Tuấn cases:", [r.data() for r in res3])

driver.close()
