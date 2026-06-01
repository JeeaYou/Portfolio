from project import create_app
app = create_app()

if __name__ == "__main__":
    # 재로더가 모듈을 두 번 로드하며 중복등록시키는지 확인 위해 잠시 끕니다.
    app.run(debug=True, use_reloader=False)
