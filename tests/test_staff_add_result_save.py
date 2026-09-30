from datetime import date

import pytest
from django.urls import reverse

from student_management_app.models import (
    CustomUser,
    Courses,
    Subjects,
    Students,
    SessionYearModel,
    StudentResult,
)
from unittest.mock import patch

pytestmark = pytest.mark.django_db(transaction=True)


# =========================================================
# FIXTURE - CENÁRIO BASE VÁLIDO
# =========================================================

@pytest.fixture
def contexto(client):
    """
    Cria todos os dados necessários para executar os testes:
    - curso
    - ano letivo
    - usuário staff
    - usuário estudante
    - disciplina
    - autenticação do staff
    """

    curso = Courses.objects.create(
        id=1,
        course_name="Engenharia de Software"
    )

    sessao = SessionYearModel.objects.create(
        id=1,
        session_start_year=date(2026, 1, 1),
        session_end_year=date(2026, 12, 31),
    )

    staff_user = CustomUser.objects.create_user(
        username="staff_teste",
        email="staff@teste.com",
        password="123456",
        user_type=2,
    )

    student_user = CustomUser.objects.create_user(
        username="student_teste",
        email="student@teste.com",
        password="123456",
        user_type=3,
    )

    estudante = Students.objects.get(admin=student_user)

    disciplina = Subjects.objects.create(
        subject_name="Teste de Software",
        course_id=curso,
        staff_id=staff_user,
    )

    client.force_login(
        staff_user,
        backend="student_management_app.EmailBackEnd.EmailBackEnd"
    )

    return {
        "client": client,
        "staff": staff_user,
        "student_user": student_user,
        "estudante": estudante,
        "disciplina": disciplina,
        "curso": curso,
        "sessao": sessao,
        "url": reverse("staff_add_result_save"),
    }


def dados_validos(contexto):
    """Retorna um POST completamente válido."""
    return {
        "student_list": str(contexto["student_user"].id),
        "subject": str(contexto["disciplina"].id),
        "assignment_marks": "75.50",
        "exam_marks": "80.50",
    }


def post_sem_excecao(contexto, dados):
    """
    Uma entrada inválida deve ser rejeitada pelo sistema,
    e não gerar uma exceção não tratada.
    """
    try:
        return contexto["client"].post(
            contexto["url"],
            data=dados
        )
    except Exception as exc:
        pytest.fail(
            f"A operação deveria ser rejeitada de forma controlada, "
            f"mas lançou {type(exc).__name__}: {exc}"
        )


# =========================================================
# PCE - PARTICIONAMENTO DE CLASSES DE EQUIVALÊNCIA
# =========================================================


# CT-PCE-01
def test_CT_PCE_01_criar_resultado_valido(contexto):
    dados = dados_validos(contexto)

    dados["assignment_marks"] = "75.50"
    dados["exam_marks"] = "80.50"

    response = contexto["client"].post(
        contexto["url"],
        data=dados
    )

    assert response.status_code == 302

    assert StudentResult.objects.count() == 1

    resultado = StudentResult.objects.get(
        student_id=contexto["estudante"],
        subject_id=contexto["disciplina"],
    )

    assert resultado.subject_assignment_marks == pytest.approx(75.50)
    assert resultado.subject_exam_marks == pytest.approx(80.50)


# CT-PCE-02
def test_CT_PCE_02_atualizar_resultado_existente(contexto):
    StudentResult.objects.create(
        student_id=contexto["estudante"],
        subject_id=contexto["disciplina"],
        subject_assignment_marks=50,
        subject_exam_marks=60,
    )

    dados = dados_validos(contexto)

    dados["assignment_marks"] = "85.50"
    dados["exam_marks"] = "90.25"

    response = contexto["client"].post(
        contexto["url"],
        data=dados
    )

    assert response.status_code == 302

    # Não deve criar duplicação
    assert StudentResult.objects.count() == 1

    resultado = StudentResult.objects.get(
        student_id=contexto["estudante"],
        subject_id=contexto["disciplina"],
    )

    assert resultado.subject_assignment_marks == pytest.approx(85.50)
    assert resultado.subject_exam_marks == pytest.approx(90.25)


# CT-PCE-03
def test_CT_PCE_03_metodo_GET_invalido(contexto):
    response = contexto["client"].get(
        contexto["url"],
        data=dados_validos(contexto),
    )

    assert response.status_code == 302
    assert StudentResult.objects.count() == 0


# ---------------------------------------------------------
# CT-PCE-04 a CT-PCE-15
#
# Regra de Ouro:
# cada parametrização altera SOMENTE UMA condição.
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "campo, valor_invalido",
    [
        pytest.param(
            "student_list",
            "",
            id="CT-PCE-04_estudante_ausente",
        ),
        pytest.param(
            "student_list",
            "999999",
            id="CT-PCE-05_estudante_inexistente",
        ),
        pytest.param(
            "subject",
            "",
            id="CT-PCE-06_disciplina_ausente",
        ),
        pytest.param(
            "subject",
            "999999",
            id="CT-PCE-07_disciplina_inexistente",
        ),
        pytest.param(
            "assignment_marks",
            "",
            id="CT-PCE-08_atividade_ausente",
        ),
        pytest.param(
            "assignment_marks",
            "abc",
            id="CT-PCE-09_atividade_nao_numerica",
        ),
        pytest.param(
            "assignment_marks",
            "-5",
            id="CT-PCE-10_atividade_abaixo_faixa",
        ),
        pytest.param(
            "assignment_marks",
            "105",
            id="CT-PCE-11_atividade_acima_faixa",
        ),
        pytest.param(
            "exam_marks",
            "",
            id="CT-PCE-12_exame_ausente",
        ),
        pytest.param(
            "exam_marks",
            "abc",
            id="CT-PCE-13_exame_nao_numerico",
        ),
        pytest.param(
            "exam_marks",
            "-5",
            id="CT-PCE-14_exame_abaixo_faixa",
        ),
        pytest.param(
            "exam_marks",
            "105",
            id="CT-PCE-15_exame_acima_faixa",
        ),
    ],
)
def test_PCE_entradas_invalidas(
    contexto,
    campo,
    valor_invalido,
):
    dados = dados_validos(contexto)

    # Somente UMA entrada é invalidada
    dados[campo] = valor_invalido

    response = post_sem_excecao(
        contexto,
        dados,
    )

    # A operação deve ser rejeitada
    assert response.status_code == 302

    # Nenhum resultado pode ser criado
    assert StudentResult.objects.count() == 0


# =========================================================
# AVL - ANÁLISE DO VALOR LIMITE
# =========================================================


# ---------------------------------------------------------
# ATIVIDADE
# CT-AVL-01 a CT-AVL-04
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "nota",
    [
        pytest.param(
            "0",
            id="CT-AVL-01_atividade_limite_inferior",
        ),
        pytest.param(
            "0.01",
            id="CT-AVL-02_atividade_acima_limite_inferior",
        ),
        pytest.param(
            "99.99",
            id="CT-AVL-03_atividade_abaixo_limite_superior",
        ),
        pytest.param(
            "100",
            id="CT-AVL-04_atividade_limite_superior",
        ),
    ],
)
def test_AVL_atividade_valores_validos(
    contexto,
    nota,
):
    dados = dados_validos(contexto)

    dados["assignment_marks"] = nota

    response = contexto["client"].post(
        contexto["url"],
        data=dados,
    )

    assert response.status_code == 302

    resultado = StudentResult.objects.get(
        student_id=contexto["estudante"],
        subject_id=contexto["disciplina"],
    )

    assert resultado.subject_assignment_marks == pytest.approx(
        float(nota)
    )


# ---------------------------------------------------------
# ATIVIDADE INVÁLIDA
# CT-AVL-05 e CT-AVL-06
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "nota",
    [
        pytest.param(
            "-0.01",
            id="CT-AVL-05_atividade_abaixo_limite_inferior",
        ),
        pytest.param(
            "100.01",
            id="CT-AVL-06_atividade_acima_limite_superior",
        ),
    ],
)
def test_AVL_atividade_valores_invalidos(
    contexto,
    nota,
):
    dados = dados_validos(contexto)

    # Somente assignment_marks é inválido
    dados["assignment_marks"] = nota

    response = post_sem_excecao(
        contexto,
        dados,
    )

    assert response.status_code == 302

    # Valor fora da faixa não pode ser salvo
    assert StudentResult.objects.count() == 0


# ---------------------------------------------------------
# EXAME
# CT-AVL-07 a CT-AVL-13
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "nota, relacao_aprovacao",
    [
        pytest.param(
            "0",
            None,
            id="CT-AVL-07_exame_limite_inferior",
        ),
        pytest.param(
            "0.01",
            None,
            id="CT-AVL-08_exame_acima_limite_inferior",
        ),
        pytest.param(
            "39.99",
            "abaixo",
            id="CT-AVL-09_exame_abaixo_limite_aprovacao",
        ),
        pytest.param(
            "40",
            "igual",
            id="CT-AVL-10_exame_limite_aprovacao",
        ),
        pytest.param(
            "40.01",
            "acima",
            id="CT-AVL-11_exame_acima_limite_aprovacao",
        ),
        pytest.param(
            "99.99",
            None,
            id="CT-AVL-12_exame_abaixo_limite_superior",
        ),
        pytest.param(
            "100",
            None,
            id="CT-AVL-13_exame_limite_superior",
        ),
    ],
)
def test_AVL_exame_valores_validos(
    contexto,
    nota,
    relacao_aprovacao,
):
    dados = dados_validos(contexto)

    dados["exam_marks"] = nota

    response = contexto["client"].post(
        contexto["url"],
        data=dados,
    )

    assert response.status_code == 302

    resultado = StudentResult.objects.get(
        student_id=contexto["estudante"],
        subject_id=contexto["disciplina"],
    )

    assert resultado.subject_exam_marks == pytest.approx(
        float(nota)
    )

    # Verificação específica do limite de aprovação = 40
    if relacao_aprovacao == "abaixo":
        assert resultado.subject_exam_marks < 40

    elif relacao_aprovacao == "igual":
        assert resultado.subject_exam_marks == pytest.approx(40)

    elif relacao_aprovacao == "acima":
        assert resultado.subject_exam_marks > 40


# ---------------------------------------------------------
# EXAME INVÁLIDO
# CT-AVL-14 e CT-AVL-15
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "nota",
    [
        pytest.param(
            "-0.01",
            id="CT-AVL-14_exame_abaixo_limite_inferior",
        ),
        pytest.param(
            "100.01",
            id="CT-AVL-15_exame_acima_limite_superior",
        ),
    ],
)
def test_AVL_exame_valores_invalidos(
    contexto,
    nota,
):
    dados = dados_validos(contexto)

    # Somente exam_marks é inválido
    dados["exam_marks"] = nota

    response = post_sem_excecao(
        contexto,
        dados,
    )

    assert response.status_code == 302

    # Valor fora da faixa não pode ser salvo
    assert StudentResult.objects.count() == 0

# =========================================================
# TESTES ESTRUTURAIS
# Casos derivados do grafo de fluxo de controle
# =========================================================


# ---------------------------------------------------------
# CT-EST-01
# Resultado existe -> atualização -> save() falha -> except
# ---------------------------------------------------------

def test_CT_EST_01_erro_no_save_da_atualizacao(contexto):
    """
    Objetivo estrutural:
    Exercitar o caminho excepcional do ramo em que
    o resultado já existe e seria atualizado.

    Caminho:
    POST -> resultado existe -> get -> atualização
    -> save falha -> except -> redirect
    """

    resultado = StudentResult.objects.create(
        student_id=contexto["estudante"],
        subject_id=contexto["disciplina"],
        subject_assignment_marks=50,
        subject_exam_marks=60,
    )

    dados = dados_validos(contexto)
    dados["assignment_marks"] = "85.50"
    dados["exam_marks"] = "90.25"

    # Força especificamente uma falha no save()
    # do caminho de atualização.
    with patch.object(
        StudentResult,
        "save",
        side_effect=Exception("Falha simulada no save"),
    ):
        response = contexto["client"].post(
            contexto["url"],
            data=dados,
        )

    # O except da função deve tratar a exceção
    assert response.status_code == 302

    mensagens = [
        str(m)
        for m in response.wsgi_request._messages
    ]

    assert "Failed to Add Result!" in mensagens

    # O resultado existente continua no banco
    assert StudentResult.objects.count() == 1

    # Como o save falhou, os valores originais
    # não podem ter sido persistidos.
    assert StudentResult.objects.filter(
        pk=resultado.pk,
        subject_assignment_marks=50,
        subject_exam_marks=60,
    ).exists()


# ---------------------------------------------------------
# CT-EST-02
# Falha durante exists() -> except
# ---------------------------------------------------------

def test_CT_EST_02_erro_na_verificacao_exists(contexto):
    """
    Objetivo estrutural:
    Exercitar a aresta de exceção antes da decisão
    if check_exist.

    Caminho:
    POST -> estudante -> disciplina
    -> filter().exists() falha
    -> except -> redirect
    """

    dados = dados_validos(contexto)

    with patch(
        "student_management_app.StaffViews."
        "StudentResult.objects.filter"
    ) as mock_filter:

        mock_filter.return_value.exists.side_effect = Exception(
            "Falha simulada no exists"
        )

        response = contexto["client"].post(
            contexto["url"],
            data=dados,
        )

    assert response.status_code == 302

    mensagens = [
        str(m)
        for m in response.wsgi_request._messages
    ]

    assert "Failed to Add Result!" in mensagens

    # Nenhum resultado deve ter sido criado
    assert StudentResult.objects.count() == 0


# ---------------------------------------------------------
# CT-EST-03
# exists() = True -> get() falha -> except
# ---------------------------------------------------------

def test_CT_EST_03_erro_ao_buscar_resultado_existente(contexto):
    """
    Objetivo estrutural:
    Exercitar o caminho em que a verificação indica
    que o resultado existe, mas ocorre uma exceção ao
    recuperá-lo.

    Caminho:
    POST -> resultado existe
    -> get falha
    -> except -> redirect
    """

    resultado = StudentResult.objects.create(
        student_id=contexto["estudante"],
        subject_id=contexto["disciplina"],
        subject_assignment_marks=50,
        subject_exam_marks=60,
    )

    dados = dados_validos(contexto)

    with patch(
        "student_management_app.StaffViews."
        "StudentResult.objects.get",
        side_effect=Exception(
            "Falha simulada ao recuperar resultado"
        ),
    ):
        response = contexto["client"].post(
            contexto["url"],
            data=dados,
        )

    assert response.status_code == 302

    mensagens = [
        str(m)
        for m in response.wsgi_request._messages
    ]

    assert "Failed to Add Result!" in mensagens

    # Nenhum novo registro deve aparecer
    assert StudentResult.objects.count() == 1

    # Registro original permanece inalterado
    assert StudentResult.objects.filter(
        pk=resultado.pk,
        subject_assignment_marks=50,
        subject_exam_marks=60,
    ).exists()
