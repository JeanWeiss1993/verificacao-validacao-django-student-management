from datetime import date

import pytest
from django.urls import reverse

from student_management_app.models import (
    Attendance,
    AttendanceReport,
    Courses,
    CustomUser,
    SessionYearModel,
    Students,
    Subjects,
)


pytestmark = pytest.mark.django_db(transaction=True)
from unittest.mock import patch

# =========================================================
# FIXTURE - CENÁRIO BASE
# =========================================================

@pytest.fixture
def contexto(client):

    # Necessários antes de criar usuários Student,
    # pois o signal do projeto busca Course id=1 e Session id=1.
    curso = Courses.objects.create(
        id=1,
        course_name="Engenharia de Software"
    )

    sessao = SessionYearModel.objects.create(
        id=1,
        session_start_year=date(2026, 1, 1),
        session_end_year=date(2026, 12, 31),
    )

    outro_curso = Courses.objects.create(
        id=2,
        course_name="Outro Curso"
    )

    staff_user = CustomUser.objects.create_user(
        username="staff_attendance",
        email="staff_attendance@teste.com",
        password="123456",
        user_type=2,
    )

    student_user = CustomUser.objects.create_user(
        username="student_attendance",
        email="student_attendance@teste.com",
        password="123456",
        user_type=3,
    )

    outro_student_user = CustomUser.objects.create_user(
        username="outro_student",
        email="outro_student@teste.com",
        password="123456",
        user_type=3,
    )

    estudante = Students.objects.get(admin=student_user)
    outro_estudante = Students.objects.get(admin=outro_student_user)

    disciplina = Subjects.objects.create(
        subject_name="Teste de Software",
        course_id=curso,
        staff_id=staff_user,
    )

    outra_disciplina = Subjects.objects.create(
        subject_name="Engenharia de Software",
        course_id=curso,
        staff_id=staff_user,
    )

    disciplina_outro_curso = Subjects.objects.create(
        subject_name="Disciplina Outro Curso",
        course_id=outro_curso,
        staff_id=staff_user,
    )

    client.force_login(
        student_user,
        backend="student_management_app.EmailBackEnd.EmailBackEnd"
    )

    return {
        "client": client,
        "curso": curso,
        "outro_curso": outro_curso,
        "sessao": sessao,
        "staff": staff_user,
        "student_user": student_user,
        "estudante": estudante,
        "outro_estudante": outro_estudante,
        "disciplina": disciplina,
        "outra_disciplina": outra_disciplina,
        "disciplina_outro_curso": disciplina_outro_curso,
        "url": reverse("student_view_attendance_post"),
    }


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def dados_validos(contexto):
    return {
        "subject": str(contexto["disciplina"].id),
        "start_date": "2026-03-10",
        "end_date": "2026-03-20",
    }


def criar_registro(
    contexto,
    data_registro,
    estudante=None,
    disciplina=None,
    status=True,
):
    """
    Cria Attendance + AttendanceReport.
    """

    if estudante is None:
        estudante = contexto["estudante"]

    if disciplina is None:
        disciplina = contexto["disciplina"]

    attendance = Attendance.objects.create(
        subject_id=disciplina,
        attendance_date=data_registro,
        session_year_id=contexto["sessao"],
    )

    return AttendanceReport.objects.create(
        student_id=estudante,
        attendance_id=attendance,
        status=status,
    )


def relatorios_da_resposta(response):
    """
    Retorna os relatórios enviados pelo contexto da view.
    """

    if response.context is None:
        return []

    if "attendance_reports" not in response.context:
        return []

    return list(response.context["attendance_reports"])


def post_sem_excecao(contexto, dados):
    """
    Entrada inválida deve ser rejeitada de forma controlada,
    não gerar exceção não tratada.
    """

    try:
        return contexto["client"].post(
            contexto["url"],
            data=dados,
        )

    except Exception as exc:
        pytest.fail(
            f"A consulta deveria ser rejeitada de forma controlada, "
            f"mas lançou {type(exc).__name__}: {exc}"
        )


def assert_consulta_rejeitada(response):
    """
    Considera rejeição controlada um redirecionamento ou resposta 4xx.
    Uma resposta 200 representa consulta aceita.
    """

    assert 300 <= response.status_code < 500
    assert relatorios_da_resposta(response) == []


# =========================================================
# PCE - PARTICIONAMENTO DE CLASSES DE EQUIVALÊNCIA
# =========================================================


# CT-PCE-01
def test_CT_PCE_01_consulta_valida_com_registros(contexto):

    esperado = criar_registro(
        contexto,
        date(2026, 3, 15),
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    assert response.status_code == 200

    relatorios = relatorios_da_resposta(response)

    assert esperado in relatorios
    assert len(relatorios) == 1


# CT-PCE-02
def test_CT_PCE_02_consulta_valida_sem_registros(contexto):

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    assert response.status_code == 200
    assert relatorios_da_resposta(response) == []


# CT-PCE-03
def test_CT_PCE_03_metodo_GET_invalido(contexto):

    response = contexto["client"].get(
        contexto["url"],
        data=dados_validos(contexto),
    )

    assert response.status_code == 302
    assert relatorios_da_resposta(response) == []


# ---------------------------------------------------------
# CT-PCE-04 e CT-PCE-05
# Disciplina ausente / inexistente
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "subject",
    [
        pytest.param(
            "",
            id="CT-PCE-04_disciplina_ausente",
        ),
        pytest.param(
            "999999",
            id="CT-PCE-05_disciplina_inexistente",
        ),
    ],
)
def test_PCE_disciplina_invalida(
    contexto,
    subject,
):

    dados = dados_validos(contexto)

    # Regra de Ouro:
    # somente subject é alterado
    dados["subject"] = subject

    response = post_sem_excecao(
        contexto,
        dados,
    )

    assert_consulta_rejeitada(response)


# CT-PCE-06
def test_CT_PCE_06_disciplina_de_outro_curso(contexto):

    dados = dados_validos(contexto)

    dados["subject"] = str(
        contexto["disciplina_outro_curso"].id
    )

    # Cria inclusive um registro para mostrar que,
    # apesar de existir, ele não deveria ser acessível
    criar_registro(
        contexto,
        date(2026, 3, 15),
        disciplina=contexto["disciplina_outro_curso"],
    )

    response = post_sem_excecao(
        contexto,
        dados,
    )

    assert_consulta_rejeitada(response)


# ---------------------------------------------------------
# CT-PCE-07 a CT-PCE-12
# Datas ausentes, formato inválido e data inexistente
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "campo, valor",
    [
        pytest.param(
            "start_date",
            "",
            id="CT-PCE-07_data_inicial_ausente",
        ),
        pytest.param(
            "start_date",
            "10/03/2026",
            id="CT-PCE-08_data_inicial_formato_invalido",
        ),
        pytest.param(
            "start_date",
            "2026-02-30",
            id="CT-PCE-09_data_inicial_inexistente",
        ),
        pytest.param(
            "end_date",
            "",
            id="CT-PCE-10_data_final_ausente",
        ),
        pytest.param(
            "end_date",
            "20/03/2026",
            id="CT-PCE-11_data_final_formato_invalido",
        ),
        pytest.param(
            "end_date",
            "2026-02-30",
            id="CT-PCE-12_data_final_inexistente",
        ),
    ],
)
def test_PCE_datas_invalidas(
    contexto,
    campo,
    valor,
):

    dados = dados_validos(contexto)

    # Regra de Ouro:
    # somente uma data fica inválida
    dados[campo] = valor

    response = post_sem_excecao(
        contexto,
        dados,
    )

    assert_consulta_rejeitada(response)


# CT-PCE-13
def test_CT_PCE_13_periodo_invertido(contexto):

    dados = dados_validos(contexto)

    dados["start_date"] = "2026-03-20"
    dados["end_date"] = "2026-03-10"

    response = post_sem_excecao(
        contexto,
        dados,
    )

    assert_consulta_rejeitada(response)


# CT-PCE-14
def test_CT_PCE_14_registro_do_estudante_autenticado(contexto):

    esperado = criar_registro(
        contexto,
        date(2026, 3, 15),
        estudante=contexto["estudante"],
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    assert esperado in relatorios


# CT-PCE-15
def test_CT_PCE_15_registro_de_outro_estudante_nao_retornado(contexto):

    outro = criar_registro(
        contexto,
        date(2026, 3, 15),
        estudante=contexto["outro_estudante"],
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    assert outro not in relatorios
    assert relatorios == []


# CT-PCE-16
def test_CT_PCE_16_registro_da_disciplina_selecionada(contexto):

    esperado = criar_registro(
        contexto,
        date(2026, 3, 15),
        disciplina=contexto["disciplina"],
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    assert esperado in relatorios_da_resposta(response)


# CT-PCE-17
def test_CT_PCE_17_registro_de_outra_disciplina_nao_retornado(contexto):

    outro = criar_registro(
        contexto,
        date(2026, 3, 15),
        disciplina=contexto["outra_disciplina"],
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    assert outro not in relatorios
    assert relatorios == []


# CT-PCE-18
def test_CT_PCE_18_registro_dentro_do_intervalo(contexto):

    esperado = criar_registro(
        contexto,
        date(2026, 3, 15),
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    assert esperado in relatorios_da_resposta(response)


# CT-PCE-19
def test_CT_PCE_19_registro_anterior_ao_intervalo(contexto):

    anterior = criar_registro(
        contexto,
        date(2026, 3, 9),
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    assert anterior not in relatorios
    assert relatorios == []


# CT-PCE-20
def test_CT_PCE_20_registro_posterior_ao_intervalo(contexto):

    posterior = criar_registro(
        contexto,
        date(2026, 3, 21),
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    assert posterior not in relatorios
    assert relatorios == []


# CT-PCE-21
def test_CT_PCE_21_status_presenca(contexto):

    esperado = criar_registro(
        contexto,
        date(2026, 3, 15),
        status=True,
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    assert esperado in relatorios
    assert esperado.status is True


# CT-PCE-22
def test_CT_PCE_22_status_ausencia(contexto):

    esperado = criar_registro(
        contexto,
        date(2026, 3, 15),
        status=False,
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    assert esperado in relatorios
    assert esperado.status is False


# =========================================================
# AVL - ANÁLISE DO VALOR LIMITE
# =========================================================


# ---------------------------------------------------------
# CT-AVL-01 a CT-AVL-06
# Limites do intervalo 10/03 a 20/03
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "data_registro, deve_retornar",
    [
        pytest.param(
            date(2026, 3, 9),
            False,
            id="CT-AVL-01_antes_limite_inicial",
        ),
        pytest.param(
            date(2026, 3, 10),
            True,
            id="CT-AVL-02_no_limite_inicial",
        ),
        pytest.param(
            date(2026, 3, 11),
            True,
            id="CT-AVL-03_apos_limite_inicial",
        ),
        pytest.param(
            date(2026, 3, 19),
            True,
            id="CT-AVL-04_antes_limite_final",
        ),
        pytest.param(
            date(2026, 3, 20),
            True,
            id="CT-AVL-05_no_limite_final",
        ),
        pytest.param(
            date(2026, 3, 21),
            False,
            id="CT-AVL-06_apos_limite_final",
        ),
    ],
)
def test_AVL_limites_intervalo(
    contexto,
    data_registro,
    deve_retornar,
):

    registro = criar_registro(
        contexto,
        data_registro,
    )

    response = contexto["client"].post(
        contexto["url"],
        data=dados_validos(contexto),
    )

    relatorios = relatorios_da_resposta(response)

    if deve_retornar:
        assert registro in relatorios
    else:
        assert registro not in relatorios
        assert relatorios == []


# CT-AVL-07
def test_CT_AVL_07_menor_intervalo_valido(contexto):

    esperado = criar_registro(
        contexto,
        date(2026, 3, 10),
    )

    dados = dados_validos(contexto)

    dados["start_date"] = "2026-03-10"
    dados["end_date"] = "2026-03-10"

    response = contexto["client"].post(
        contexto["url"],
        data=dados,
    )

    assert response.status_code == 200

    relatorios = relatorios_da_resposta(response)

    assert esperado in relatorios
    assert len(relatorios) == 1


# CT-AVL-08
def test_CT_AVL_08_limite_inversao_periodo(contexto):

    dados = dados_validos(contexto)

    dados["start_date"] = "2026-03-11"
    dados["end_date"] = "2026-03-10"

    response = post_sem_excecao(
        contexto,
        dados,
    )

    assert_consulta_rejeitada(response)

# =========================================================
# TESTES ESTRUTURAIS
# Caminhos derivados do Grafo de Fluxo de Controle
# =========================================================


# ---------------------------------------------------------
# CT-EST-01
# Falha na busca do usuário autenticado
# P6: N1 -> N2 -> N4 -> N5 -> N6 -> N7 -> N8 -> EX
# ---------------------------------------------------------

def test_CT_EST_01_erro_busca_usuario(contexto):
    """
    Objetivo estrutural:
    Exercitar a aresta excepcional da busca do usuário.

    Caminho:
    POST -> datas válidas -> disciplina válida
    -> busca do usuário falha -> término excepcional.
    """

    dados = dados_validos(contexto)

    with patch(
        "student_management_app.StudentViews."
        "CustomUser.objects.get",
        side_effect=Exception(
            "Falha simulada na busca do usuário"
        ),
    ):
        with pytest.raises(
            Exception,
            match="Falha simulada na busca do usuário",
        ):
            contexto["client"].post(
                contexto["url"],
                data=dados,
            )


# ---------------------------------------------------------
# CT-EST-02
# Falha na busca do estudante
# P7: N1 -> N2 -> N4 -> N5 -> N6 -> N7 -> N8 -> N9 -> EX
# ---------------------------------------------------------

def test_CT_EST_02_erro_busca_estudante(contexto):
    """
    Objetivo estrutural:
    Exercitar a aresta excepcional da busca do estudante.

    Caminho:
    POST -> datas válidas -> disciplina válida
    -> usuário encontrado -> busca do estudante falha
    -> término excepcional.
    """

    dados = dados_validos(contexto)

    with patch(
        "student_management_app.StudentViews."
        "Students.objects.get",
        side_effect=Exception(
            "Falha simulada na busca do estudante"
        ),
    ):
        with pytest.raises(
            Exception,
            match="Falha simulada na busca do estudante",
        ):
            contexto["client"].post(
                contexto["url"],
                data=dados,
            )


# ---------------------------------------------------------
# CT-EST-03
# Falha na consulta de Attendance
# P8:
# N1 -> N2 -> N4 -> N5 -> N6 -> N7 -> N8 -> N9 -> N10 -> EX
# ---------------------------------------------------------

def test_CT_EST_03_erro_consulta_attendance(contexto):
    """
    Objetivo estrutural:
    Exercitar a aresta excepcional da consulta
    dos registros de Attendance.

    Caminho:
    POST -> dados válidos -> estudante encontrado
    -> Attendance.objects.filter() falha
    -> término excepcional.
    """

    dados = dados_validos(contexto)

    with patch(
        "student_management_app.StudentViews."
        "Attendance.objects.filter",
        side_effect=Exception(
            "Falha simulada na consulta de Attendance"
        ),
    ):
        with pytest.raises(
            Exception,
            match="Falha simulada na consulta de Attendance",
        ):
            contexto["client"].post(
                contexto["url"],
                data=dados,
            )


# ---------------------------------------------------------
# CT-EST-04
# Falha na consulta de AttendanceReport
# P9:
# N1 -> N2 -> N4 -> N5 -> N6 -> N7 -> N8 -> N9
# -> N10 -> N11 -> EX
# ---------------------------------------------------------

def test_CT_EST_04_erro_consulta_attendance_report(contexto):
    """
    Objetivo estrutural:
    Exercitar a aresta excepcional da consulta
    de AttendanceReport.

    Caminho:
    POST -> dados válidos -> consulta Attendance concluída
    -> AttendanceReport.objects.filter() falha
    -> término excepcional.
    """

    dados = dados_validos(contexto)

    with patch(
        "student_management_app.StudentViews."
        "AttendanceReport.objects.filter",
        side_effect=Exception(
            "Falha simulada na consulta de AttendanceReport"
        ),
    ):
        with pytest.raises(
            Exception,
            match="Falha simulada na consulta de AttendanceReport",
        ):
            contexto["client"].post(
                contexto["url"],
                data=dados,
            )