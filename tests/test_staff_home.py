from datetime import date

import pytest
from django.urls import reverse

from student_management_app.models import (
    Attendance,
    AttendanceReport,
    Courses,
    CustomUser,
    LeaveReportStaff,
    SessionYearModel,
    Staffs,
    Students,
    Subjects,
)


pytestmark = pytest.mark.django_db(transaction=True)


# =========================================================
# FIXTURE BASE
# =========================================================

@pytest.fixture
def contexto(client):

    curso = Courses.objects.create(
        id=1,
        course_name="Engenharia de Software",
    )

    sessao = SessionYearModel.objects.create(
        id=1,
        session_start_year=date(2026, 1, 1),
        session_end_year=date(2026, 12, 31),
    )

    professor_user = CustomUser.objects.create_user(
        username="professor_teste",
        email="professor@teste.com",
        password="123456",
        user_type=2,
        first_name="Professor",
        last_name="Teste",
    )

    professor = Staffs.objects.get(
        admin=professor_user
    )

    client.force_login(
        professor_user,
        backend="student_management_app.EmailBackEnd.EmailBackEnd",
    )

    return {
        "client": client,
        "curso": curso,
        "sessao": sessao,
        "professor_user": professor_user,
        "professor": professor,
        "url": reverse("staff_home"),
    }


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def criar_curso(nome):
    return Courses.objects.create(
        course_name=nome
    )


def criar_disciplina(
    contexto,
    nome,
    curso=None,
    professor_user=None,
):
    if curso is None:
        curso = contexto["curso"]

    if professor_user is None:
        professor_user = contexto["professor_user"]

    return Subjects.objects.create(
        subject_name=nome,
        course_id=curso,
        staff_id=professor_user,
    )


def criar_estudante(
    contexto,
    username,
    curso=None,
):
    if curso is None:
        curso = contexto["curso"]

    user = CustomUser.objects.create_user(
        username=username,
        email=f"{username}@teste.com",
        password="123456",
        user_type=3,
        first_name=username,
        last_name="Teste",
    )

    estudante = Students.objects.get(
        admin=user
    )

    # O signal do projeto cria todo estudante inicialmente
    # no curso id=1. Aqui ajustamos para o curso desejado.
    estudante.course_id = curso
    estudante.save()

    return estudante


def criar_frequencia(
    contexto,
    disciplina,
    data_frequencia,
    estudante=None,
    status=None,
):
    frequencia = Attendance.objects.create(
        subject_id=disciplina,
        attendance_date=data_frequencia,
        session_year_id=contexto["sessao"],
    )

    relatorio = None

    if estudante is not None and status is not None:
        relatorio = AttendanceReport.objects.create(
            student_id=estudante,
            attendance_id=frequencia,
            status=status,
        )

    return frequencia, relatorio


def criar_licenca(
    contexto,
    status,
    data="2026-03-10",
):
    return LeaveReportStaff.objects.create(
        staff_id=contexto["professor"],
        leave_date=data,
        leave_message="Teste",
        leave_status=status,
    )


def abrir_dashboard(contexto):
    response = contexto["client"].get(
        contexto["url"]
    )

    assert response.status_code == 200

    return response


def get_sem_excecao(contexto):
    try:
        return contexto["client"].get(
            contexto["url"]
        )

    except Exception as exc:
        pytest.fail(
            "O dashboard deveria rejeitar a operação "
            "de forma controlada, mas lançou "
            f"{type(exc).__name__}: {exc}"
        )


def nome_estudante(estudante):
    return (
        estudante.admin.first_name
        + " "
        + estudante.admin.last_name
    )


# =========================================================
# PCE
# PARTICIONAMENTO DE CLASSES DE EQUIVALÊNCIA
# =========================================================


# ---------------------------------------------------------
# CT-PCE-01
# Professor válido sem disciplinas
# ---------------------------------------------------------

def test_CT_PCE_01_professor_sem_disciplinas(contexto):

    response = abrir_dashboard(contexto)

    assert response.context["subject_count"] == 0
    assert response.context["students_count"] == 0
    assert response.context["attendance_count"] == 0

    assert response.context["subject_list"] == []
    assert response.context["attendance_list"] == []
    assert response.context["student_list"] == []


# ---------------------------------------------------------
# CT-PCE-02
# Uma disciplina vinculada
# ---------------------------------------------------------

def test_CT_PCE_02_uma_disciplina(contexto):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    response = abrir_dashboard(contexto)

    assert response.context["subject_count"] == 1
    assert response.context["subject_list"] == [
        disciplina.subject_name
    ]


# ---------------------------------------------------------
# CT-PCE-03
# Múltiplas disciplinas
# ---------------------------------------------------------

def test_CT_PCE_03_multiplas_disciplinas(contexto):

    d1 = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    d2 = criar_disciplina(
        contexto,
        "Qualidade de Software",
    )

    response = abrir_dashboard(contexto)

    assert response.context["subject_count"] == 2

    assert set(
        response.context["subject_list"]
    ) == {
        d1.subject_name,
        d2.subject_name,
    }


# ---------------------------------------------------------
# CT-PCE-04
# Disciplina de outro professor
# ---------------------------------------------------------

def test_CT_PCE_04_disciplina_outro_professor(contexto):

    propria = criar_disciplina(
        contexto,
        "Disciplina Própria",
    )

    outro_professor = CustomUser.objects.create_user(
        username="outro_professor",
        email="outro_professor@teste.com",
        password="123456",
        user_type=2,
    )

    criar_disciplina(
        contexto,
        "Disciplina Outro Professor",
        professor_user=outro_professor,
    )

    response = abrir_dashboard(contexto)

    assert response.context["subject_count"] == 1

    assert response.context["subject_list"] == [
        propria.subject_name
    ]


# ---------------------------------------------------------
# CT-PCE-05
# Duas disciplinas no mesmo curso
# ---------------------------------------------------------

def test_CT_PCE_05_disciplinas_mesmo_curso(contexto):

    criar_disciplina(
        contexto,
        "Disciplina A",
    )

    criar_disciplina(
        contexto,
        "Disciplina B",
    )

    criar_estudante(
        contexto,
        "aluno1",
    )

    response = abrir_dashboard(contexto)

    # O mesmo curso deve ser considerado uma única vez
    assert response.context["students_count"] == 1


# ---------------------------------------------------------
# CT-PCE-06
# Disciplinas em cursos diferentes
# ---------------------------------------------------------

def test_CT_PCE_06_disciplinas_cursos_diferentes(contexto):

    curso2 = criar_curso(
        "Ciência da Computação"
    )

    criar_disciplina(
        contexto,
        "Disciplina Curso 1",
        curso=contexto["curso"],
    )

    criar_disciplina(
        contexto,
        "Disciplina Curso 2",
        curso=curso2,
    )

    criar_estudante(
        contexto,
        "aluno_curso1",
        curso=contexto["curso"],
    )

    criar_estudante(
        contexto,
        "aluno_curso2",
        curso=curso2,
    )

    response = abrir_dashboard(contexto)

    assert response.context["students_count"] == 2


# ---------------------------------------------------------
# CT-PCE-07
# Nenhum estudante
# ---------------------------------------------------------

def test_CT_PCE_07_nenhum_estudante(contexto):

    criar_disciplina(
        contexto,
        "Teste de Software",
    )

    response = abrir_dashboard(contexto)

    assert response.context["students_count"] == 0
    assert response.context["student_list"] == []


# ---------------------------------------------------------
# CT-PCE-08
# Um estudante
# ---------------------------------------------------------

def test_CT_PCE_08_um_estudante(contexto):

    criar_disciplina(
        contexto,
        "Teste de Software",
    )

    estudante = criar_estudante(
        contexto,
        "aluno1",
    )

    response = abrir_dashboard(contexto)

    assert response.context["students_count"] == 1

    assert response.context["student_list"] == [
        nome_estudante(estudante)
    ]


# ---------------------------------------------------------
# CT-PCE-09
# Múltiplos estudantes
# ---------------------------------------------------------

def test_CT_PCE_09_multiplos_estudantes(contexto):

    criar_disciplina(
        contexto,
        "Teste de Software",
    )

    criar_estudante(
        contexto,
        "aluno1",
    )

    criar_estudante(
        contexto,
        "aluno2",
    )

    response = abrir_dashboard(contexto)

    assert response.context["students_count"] == 2


# ---------------------------------------------------------
# CT-PCE-10
# Estudante de curso não associado
# ---------------------------------------------------------

def test_CT_PCE_10_estudante_curso_nao_associado(contexto):

    outro_curso = criar_curso(
        "Curso Não Associado"
    )

    criar_disciplina(
        contexto,
        "Teste de Software",
        curso=contexto["curso"],
    )

    estudante_valido = criar_estudante(
        contexto,
        "aluno_valido",
        curso=contexto["curso"],
    )

    estudante_outro = criar_estudante(
        contexto,
        "aluno_outro",
        curso=outro_curso,
    )

    response = abrir_dashboard(contexto)

    assert response.context["students_count"] == 1

    nomes = response.context["student_list"]

    assert nome_estudante(estudante_valido) in nomes
    assert nome_estudante(estudante_outro) not in nomes


# ---------------------------------------------------------
# CT-PCE-11
# Nenhuma frequência
# ---------------------------------------------------------

def test_CT_PCE_11_nenhuma_frequencia(contexto):

    criar_disciplina(
        contexto,
        "Teste de Software",
    )

    response = abrir_dashboard(contexto)

    assert response.context["attendance_count"] == 0


# ---------------------------------------------------------
# CT-PCE-12
# Uma frequência
# ---------------------------------------------------------

def test_CT_PCE_12_uma_frequencia(contexto):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 10),
    )

    response = abrir_dashboard(contexto)

    assert response.context["attendance_count"] == 1
    assert response.context["attendance_list"] == [1]


# ---------------------------------------------------------
# CT-PCE-13
# Múltiplas frequências
# ---------------------------------------------------------

def test_CT_PCE_13_multiplas_frequencias(contexto):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 10),
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 11),
    )

    response = abrir_dashboard(contexto)

    assert response.context["attendance_count"] == 2
    assert response.context["attendance_list"] == [2]


# ---------------------------------------------------------
# CT-PCE-14
# Frequência de disciplina de outro professor
# ---------------------------------------------------------

def test_CT_PCE_14_frequencia_outro_professor(contexto):

    disciplina_propria = criar_disciplina(
        contexto,
        "Disciplina Própria",
    )

    outro_professor = CustomUser.objects.create_user(
        username="professor2",
        email="professor2@teste.com",
        password="123456",
        user_type=2,
    )

    disciplina_outro = criar_disciplina(
        contexto,
        "Disciplina Outro Professor",
        professor_user=outro_professor,
    )

    criar_frequencia(
        contexto,
        disciplina_propria,
        date(2026, 3, 10),
    )

    criar_frequencia(
        contexto,
        disciplina_outro,
        date(2026, 3, 11),
    )

    response = abrir_dashboard(contexto)

    assert response.context["attendance_count"] == 1
    assert response.context["attendance_list"] == [1]


# ---------------------------------------------------------
# CT-PCE-15
# Nenhuma licença aprovada
# ---------------------------------------------------------

def test_CT_PCE_15_nenhuma_licenca_aprovada(contexto):

    response = abrir_dashboard(contexto)

    assert response.context["leave_count"] == 0


# ---------------------------------------------------------
# CT-PCE-16
# Uma licença aprovada
# ---------------------------------------------------------

def test_CT_PCE_16_licenca_aprovada(contexto):

    criar_licenca(
        contexto,
        status=1,
    )

    response = abrir_dashboard(contexto)

    assert response.context["leave_count"] == 1


# ---------------------------------------------------------
# CT-PCE-17
# Licença não aprovada
# ---------------------------------------------------------

def test_CT_PCE_17_licenca_nao_aprovada(contexto):

    criar_licenca(
        contexto,
        status=0,
    )

    response = abrir_dashboard(contexto)

    assert response.context["leave_count"] == 0


# ---------------------------------------------------------
# CT-PCE-18
# Presença
# ---------------------------------------------------------

def test_CT_PCE_18_presenca(contexto):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    estudante = criar_estudante(
        contexto,
        "aluno1",
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 10),
        estudante=estudante,
        status=True,
    )

    response = abrir_dashboard(contexto)

    assert response.context[
        "attendance_present_list"
    ] == [1]

    assert response.context[
        "attendance_absent_list"
    ] == [0]


# ---------------------------------------------------------
# CT-PCE-19
# Ausência
# ---------------------------------------------------------

def test_CT_PCE_19_ausencia(contexto):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    estudante = criar_estudante(
        contexto,
        "aluno1",
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 10),
        estudante=estudante,
        status=False,
    )

    response = abrir_dashboard(contexto)

    assert response.context[
        "attendance_present_list"
    ] == [0]

    assert response.context[
        "attendance_absent_list"
    ] == [1]


# ---------------------------------------------------------
# CT-PCE-20
# Presença e ausência
# ---------------------------------------------------------

def test_CT_PCE_20_presenca_e_ausencia(contexto):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    estudante = criar_estudante(
        contexto,
        "aluno1",
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 10),
        estudante=estudante,
        status=True,
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 11),
        estudante=estudante,
        status=False,
    )

    response = abrir_dashboard(contexto)

    assert response.context[
        "attendance_present_list"
    ] == [1]

    assert response.context[
        "attendance_absent_list"
    ] == [1]


# ---------------------------------------------------------
# CT-PCE-21
# Estudante sem registros
# ---------------------------------------------------------

def test_CT_PCE_21_estudante_sem_registros(contexto):

    criar_disciplina(
        contexto,
        "Teste de Software",
    )

    criar_estudante(
        contexto,
        "aluno1",
    )

    response = abrir_dashboard(contexto)

    assert response.context[
        "attendance_present_list"
    ] == [0]

    assert response.context[
        "attendance_absent_list"
    ] == [0]


# ---------------------------------------------------------
# CT-PCE-22
# Correspondência disciplina x frequência
# ---------------------------------------------------------

def test_CT_PCE_22_correspondencia_disciplina_frequencia(
    contexto,
):

    disciplina_a = criar_disciplina(
        contexto,
        "Disciplina A",
    )

    disciplina_b = criar_disciplina(
        contexto,
        "Disciplina B",
    )

    criar_frequencia(
        contexto,
        disciplina_a,
        date(2026, 3, 10),
    )

    criar_frequencia(
        contexto,
        disciplina_b,
        date(2026, 3, 10),
    )

    criar_frequencia(
        contexto,
        disciplina_b,
        date(2026, 3, 11),
    )

    response = abrir_dashboard(contexto)

    resultado = dict(
        zip(
            response.context["subject_list"],
            response.context["attendance_list"],
        )
    )

    assert resultado["Disciplina A"] == 1
    assert resultado["Disciplina B"] == 2


# ---------------------------------------------------------
# CT-PCE-23
# Correspondência estudante x frequência
# ---------------------------------------------------------

def test_CT_PCE_23_correspondencia_estudante_frequencia(
    contexto,
):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    aluno1 = criar_estudante(
        contexto,
        "aluno1",
    )

    aluno2 = criar_estudante(
        contexto,
        "aluno2",
    )

    # Aluno 1: 2 presenças
    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 10),
        estudante=aluno1,
        status=True,
    )

    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 11),
        estudante=aluno1,
        status=True,
    )

    # Aluno 2: 1 ausência
    criar_frequencia(
        contexto,
        disciplina,
        date(2026, 3, 12),
        estudante=aluno2,
        status=False,
    )

    response = abrir_dashboard(contexto)

    resultado = {}

    for nome, presentes, ausentes in zip(
        response.context["student_list"],
        response.context["attendance_present_list"],
        response.context["attendance_absent_list"],
    ):
        resultado[nome] = {
            "presentes": presentes,
            "ausentes": ausentes,
        }

    assert resultado[
        nome_estudante(aluno1)
    ] == {
        "presentes": 2,
        "ausentes": 0,
    }

    assert resultado[
        nome_estudante(aluno2)
    ] == {
        "presentes": 0,
        "ausentes": 1,
    }


# ---------------------------------------------------------
# CT-PCE-24
# Professor sem cadastro Staff
# ---------------------------------------------------------

def test_CT_PCE_24_professor_sem_cadastro_staff(contexto):

    # Remove apenas o registro Staffs.
    # O CustomUser continua autenticado como professor.
    contexto["professor"].delete()

    response = get_sem_excecao(contexto)

    # O sistema deveria rejeitar/tratar a situação
    # sem gerar erro interno.
    assert 300 <= response.status_code < 500


# =========================================================
# AVL
# ANÁLISE DO VALOR LIMITE
# =========================================================


# ---------------------------------------------------------
# CT-AVL-01 a CT-AVL-03
# Quantidade de disciplinas: 0, 1 e 2
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "quantidade",
    [
        pytest.param(
            0,
            id="CT-AVL-01_zero_disciplinas",
        ),
        pytest.param(
            1,
            id="CT-AVL-02_primeira_disciplina",
        ),
        pytest.param(
            2,
            id="CT-AVL-03_mais_de_uma_disciplina",
        ),
    ],
)
def test_AVL_quantidade_disciplinas(
    contexto,
    quantidade,
):

    for i in range(quantidade):
        criar_disciplina(
            contexto,
            f"Disciplina {i + 1}",
        )

    response = abrir_dashboard(contexto)

    assert response.context[
        "subject_count"
    ] == quantidade

    assert len(
        response.context["subject_list"]
    ) == quantidade


# ---------------------------------------------------------
# CT-AVL-04 a CT-AVL-06
# Quantidade de cursos associados: 0, 1 e 2
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "quantidade",
    [
        pytest.param(
            0,
            id="CT-AVL-04_zero_cursos",
        ),
        pytest.param(
            1,
            id="CT-AVL-05_primeiro_curso",
        ),
        pytest.param(
            2,
            id="CT-AVL-06_mais_de_um_curso",
        ),
    ],
)
def test_AVL_quantidade_cursos(
    contexto,
    quantidade,
):

    if quantidade >= 1:

        criar_disciplina(
            contexto,
            "Disciplina Curso 1",
            curso=contexto["curso"],
        )

        criar_estudante(
            contexto,
            "aluno_curso1",
            curso=contexto["curso"],
        )

    if quantidade >= 2:

        curso2 = criar_curso(
            "Curso 2"
        )

        criar_disciplina(
            contexto,
            "Disciplina Curso 2",
            curso=curso2,
        )

        criar_estudante(
            contexto,
            "aluno_curso2",
            curso=curso2,
        )

    response = abrir_dashboard(contexto)

    assert response.context[
        "students_count"
    ] == quantidade


# ---------------------------------------------------------
# CT-AVL-07 a CT-AVL-09
# Quantidade de estudantes: 0, 1 e 2
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "quantidade",
    [
        pytest.param(
            0,
            id="CT-AVL-07_zero_estudantes",
        ),
        pytest.param(
            1,
            id="CT-AVL-08_primeiro_estudante",
        ),
        pytest.param(
            2,
            id="CT-AVL-09_mais_de_um_estudante",
        ),
    ],
)
def test_AVL_quantidade_estudantes(
    contexto,
    quantidade,
):

    criar_disciplina(
        contexto,
        "Teste de Software",
    )

    for i in range(quantidade):
        criar_estudante(
            contexto,
            f"aluno{i + 1}",
        )

    response = abrir_dashboard(contexto)

    assert response.context[
        "students_count"
    ] == quantidade


# ---------------------------------------------------------
# CT-AVL-10 a CT-AVL-12
# Quantidade de frequências: 0, 1 e 2
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "quantidade",
    [
        pytest.param(
            0,
            id="CT-AVL-10_zero_frequencias",
        ),
        pytest.param(
            1,
            id="CT-AVL-11_primeiro_registro_frequencia",
        ),
        pytest.param(
            2,
            id="CT-AVL-12_mais_de_um_registro_frequencia",
        ),
    ],
)
def test_AVL_quantidade_frequencias(
    contexto,
    quantidade,
):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    for i in range(quantidade):
        criar_frequencia(
            contexto,
            disciplina,
            date(2026, 3, 10 + i),
        )

    response = abrir_dashboard(contexto)

    assert response.context[
        "attendance_count"
    ] == quantidade

    assert response.context[
        "attendance_list"
    ] == [quantidade]


# ---------------------------------------------------------
# CT-AVL-13 a CT-AVL-15
# Licenças aprovadas: 0, 1 e 2
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "quantidade",
    [
        pytest.param(
            0,
            id="CT-AVL-13_zero_licencas_aprovadas",
        ),
        pytest.param(
            1,
            id="CT-AVL-14_primeira_licenca_aprovada",
        ),
        pytest.param(
            2,
            id="CT-AVL-15_mais_de_uma_licenca_aprovada",
        ),
    ],
)
def test_AVL_licencas_aprovadas(
    contexto,
    quantidade,
):

    for i in range(quantidade):
        criar_licenca(
            contexto,
            status=1,
            data=f"2026-03-{10 + i:02d}",
        )

    response = abrir_dashboard(contexto)

    assert response.context[
        "leave_count"
    ] == quantidade


# ---------------------------------------------------------
# CT-AVL-16 a CT-AVL-18
# Presenças: 0, 1 e 2
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "quantidade",
    [
        pytest.param(
            0,
            id="CT-AVL-16_zero_presencas",
        ),
        pytest.param(
            1,
            id="CT-AVL-17_primeira_presenca",
        ),
        pytest.param(
            2,
            id="CT-AVL-18_mais_de_uma_presenca",
        ),
    ],
)
def test_AVL_quantidade_presencas(
    contexto,
    quantidade,
):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    estudante = criar_estudante(
        contexto,
        "aluno1",
    )

    if quantidade == 0:
        # Há um registro, mas ele é ausência.
        # Assim confirmamos especificamente zero presenças.
        criar_frequencia(
            contexto,
            disciplina,
            date(2026, 3, 10),
            estudante=estudante,
            status=False,
        )

    else:
        for i in range(quantidade):
            criar_frequencia(
                contexto,
                disciplina,
                date(2026, 3, 10 + i),
                estudante=estudante,
                status=True,
            )

    response = abrir_dashboard(contexto)

    assert response.context[
        "attendance_present_list"
    ] == [quantidade]


# ---------------------------------------------------------
# CT-AVL-19 a CT-AVL-21
# Ausências: 0, 1 e 2
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "quantidade",
    [
        pytest.param(
            0,
            id="CT-AVL-19_zero_ausencias",
        ),
        pytest.param(
            1,
            id="CT-AVL-20_primeira_ausencia",
        ),
        pytest.param(
            2,
            id="CT-AVL-21_mais_de_uma_ausencia",
        ),
    ],
)
def test_AVL_quantidade_ausencias(
    contexto,
    quantidade,
):

    disciplina = criar_disciplina(
        contexto,
        "Teste de Software",
    )

    estudante = criar_estudante(
        contexto,
        "aluno1",
    )

    if quantidade == 0:
        # Há um registro, mas ele é presença.
        # Assim confirmamos especificamente zero ausências.
        criar_frequencia(
            contexto,
            disciplina,
            date(2026, 3, 10),
            estudante=estudante,
            status=True,
        )

    else:
        for i in range(quantidade):
            criar_frequencia(
                contexto,
                disciplina,
                date(2026, 3, 10 + i),
                estudante=estudante,
                status=False,
            )

    response = abrir_dashboard(contexto)

    assert response.context[
        "attendance_absent_list"
    ] == [quantidade]