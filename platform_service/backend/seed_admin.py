import os
import shutil
from app.database import SessionLocal
from app.models.user import User
from app.models.course_material import CourseMaterial
from app.models.course import Course, Lesson
from app.models.homework import Homework
from app.services.auth_service import get_password_hash

db = SessionLocal()

# Add Admin
admin_user = db.query(User).filter(User.username == "admin").first()
if not admin_user:
    print("Создаем администратора (admin/admin)...")
    admin_user = User(
        username="admin",
        password_hash=get_password_hash("admin"),
        role="admin",
        full_name="System Administrator"
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
else:
    print("Администратор уже существует.")

# Link the existing PDF
pdf_src = r"C:\Users\liner\Desktop\Diplom\mr-osnovy-algoritmizatsii-i-programm.pdf"
dest_dir = r"C:\Users\liner\Desktop\Diplom\platform_service\backend\uploads\materials"
os.makedirs(dest_dir, exist_ok=True)

material_id = "mr_osnovy"
dest_path = os.path.join(dest_dir, f"{material_id}.pdf")

if os.path.exists(pdf_src):
    shutil.copy2(pdf_src, dest_path)
    print(f"Файл скопирован в {dest_path}")

    existing = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    if not existing:
        material = CourseMaterial(
            id=material_id,
            course_id="python",
            title="mr-osnovy-algoritmizatsii-i-programm.pdf",
            file_path=dest_path,
            source_type="methodology"
        )
        db.add(material)
        db.commit()
        print("Запись о методичке добавлена в базу данных Платформы.")
    else:
        print("Запись о методичке уже существует.")
else:
    print("Внимание: исходный PDF не найден.")

db.close()
