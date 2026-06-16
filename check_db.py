from project import create_app
from project.models import Project  # 모델 import

app = create_app()
with app.app_context():
    rows = Project.query.all()
    for p in rows:
        print(p.id, p.ko_name, p.en_name, p.zh_name)
