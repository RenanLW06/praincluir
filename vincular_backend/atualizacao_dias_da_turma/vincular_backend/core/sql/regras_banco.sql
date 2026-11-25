-- =====================================================================
-- Regras do Vincular que vivem no banco (idempotente: pode rodar sempre).
-- Aplicado automaticamente ao final de `python manage.py migrate`.
--
-- O backend informa quem está operando, na mesma transação:
--     SELECT set_config('app.usuario_id', '<id>', true);
-- =====================================================================

-- ---------------------------------------------------------------------
-- Código V permanente
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_codigo_v_imutavel() RETURNS trigger AS $$
BEGIN
    IF NEW.codigo_v IS DISTINCT FROM OLD.codigo_v THEN
        RAISE EXCEPTION 'O Código V é permanente e não pode ser alterado (%).', OLD.codigo_v;
    END IF;
    NEW.atualizado_em := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_crianca_codigo_v ON crianca;
CREATE TRIGGER trg_crianca_codigo_v
    BEFORE UPDATE ON crianca
    FOR EACH ROW EXECUTE FUNCTION fn_codigo_v_imutavel();

-- ---------------------------------------------------------------------
-- Matrícula: capacidade, D1/D2 e conflito de horário.
-- Realocação NÃO passa por aqui (pode exceder a capacidade).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_matricula() RETURNS trigger AS $$
DECLARE
    t   turma%ROWTYPE;
    qtd INT;
BEGIN
    -- Trava a turma para evitar duas matrículas simultâneas na última vaga.
    SELECT * INTO t FROM turma WHERE id = NEW.turma_id FOR UPDATE;

    SELECT count(*) INTO qtd
    FROM matricula
    WHERE turma_id = NEW.turma_id
      AND data_fim IS NULL
      AND id IS DISTINCT FROM NEW.id;

    IF qtd >= t.capacidade THEN
        RAISE EXCEPTION 'Turma lotada: capacidade de % crianças atingida.', t.capacidade;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM matricula m JOIN turma x ON x.id = m.turma_id
        WHERE m.crianca_id = NEW.crianca_id
          AND m.data_fim IS NULL
          AND m.id IS DISTINCT FROM NEW.id
          AND x.horario <> t.horario
    ) THEN
        RAISE EXCEPTION 'A criança já tem atividades em outro horário (D1/D2); todas devem ficar no mesmo.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM matricula m JOIN turma x ON x.id = m.turma_id
        WHERE m.crianca_id = NEW.crianca_id
          AND m.data_fim IS NULL
          AND m.id IS DISTINCT FROM NEW.id
          AND x.letra <> t.letra
    ) THEN
        RAISE EXCEPTION 'A criança já está matriculada em outro dia da semana; as duas atividades devem ser no mesmo dia (outros dias só por realocação).';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM matricula m JOIN turma x ON x.id = m.turma_id
        WHERE m.crianca_id = NEW.crianca_id
          AND m.data_fim IS NULL
          AND m.id IS DISTINCT FROM NEW.id
          AND x.letra = t.letra
          AND x.horario = t.horario
          AND x.tempo = t.tempo
    ) THEN
        RAISE EXCEPTION 'A criança já tem uma atividade neste tempo; são duas atividades por dia, uma em cada tempo do mesmo horário.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_matricula_validar ON matricula;
CREATE TRIGGER trg_matricula_validar
    BEFORE INSERT OR UPDATE ON matricula
    FOR EACH ROW
    WHEN (NEW.data_fim IS NULL)
    EXECUTE FUNCTION fn_validar_matricula();

-- ---------------------------------------------------------------------
-- Realocação: só administrador; criança matriculada na turma de origem.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_realocacao() RETURNS trigger AS $$
DECLARE
    v_dia SMALLINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM usuario WHERE id = NEW.realizada_por_id AND perfil = 'administrador'
    ) THEN
        RAISE EXCEPTION 'Somente usuários com perfil administrador podem realocar.';
    END IF;

    SELECT d.dia_semana INTO v_dia
    FROM turma t JOIN dia_turma d ON d.letra = t.letra
    WHERE t.id = NEW.turma_destino_id;
    IF EXTRACT(ISODOW FROM NEW.data)::INT <> v_dia THEN
        RAISE EXCEPTION 'A turma de destino não tem aula nesta data (o dia da semana é diferente do dia da turma).';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM matricula
        WHERE crianca_id = NEW.crianca_id
          AND turma_id = NEW.turma_origem_id
          AND data_inicio <= NEW.data
          AND (data_fim IS NULL OR data_fim >= NEW.data)
    ) THEN
        RAISE EXCEPTION 'A criança não está matriculada na turma de origem nesta data.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_realocacao_validar ON realocacao;
CREATE TRIGGER trg_realocacao_validar
    BEFORE INSERT ON realocacao
    FOR EACH ROW EXECUTE FUNCTION fn_validar_realocacao();

-- ---------------------------------------------------------------------
-- Lista de chamada de uma turma em uma data:
--   matriculados (menos os realocados para fora nesse dia)
--   + realocados para esta turma nesse dia.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_lista_chamada(p_turma_id BIGINT, p_data DATE)
RETURNS TABLE (crianca_id BIGINT, nome TEXT, codigo_v TEXT, realocada BOOLEAN) AS $$
    SELECT c.id, c.nome::text, c.codigo_v::text, FALSE
    FROM matricula m
    JOIN crianca c ON c.id = m.crianca_id
    WHERE m.turma_id = p_turma_id
      AND m.data_inicio <= p_data
      AND (m.data_fim IS NULL OR m.data_fim >= p_data)
      AND c.ativo
      AND NOT EXISTS (
            SELECT 1 FROM realocacao r
            WHERE r.crianca_id = m.crianca_id
              AND r.turma_origem_id = p_turma_id
              AND r.data = p_data)
    UNION ALL
    SELECT c.id, c.nome::text, c.codigo_v::text, TRUE
    FROM realocacao r
    JOIN crianca c ON c.id = r.crianca_id
    WHERE r.turma_destino_id = p_turma_id
      AND r.data = p_data
      AND c.ativo
    ORDER BY 2;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------
-- Presença: na criação, a criança precisa estar na lista de chamada do dia.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_presenca() RETURNS trigger AS $$
DECLARE
    v_dia SMALLINT;
BEGIN
    SELECT d.dia_semana INTO v_dia
    FROM turma t JOIN dia_turma d ON d.letra = t.letra
    WHERE t.id = NEW.turma_id;
    IF EXTRACT(ISODOW FROM NEW.data)::INT <> v_dia THEN
        RAISE EXCEPTION 'Esta turma não tem aula na data informada (o dia da semana é diferente do dia da turma).';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM fn_lista_chamada(NEW.turma_id, NEW.data) l
        WHERE l.crianca_id = NEW.crianca_id
    ) THEN
        RAISE EXCEPTION 'A criança não consta na lista de chamada desta turma nesta data.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_presenca_validar ON presenca;
CREATE TRIGGER trg_presenca_validar
    BEFORE INSERT ON presenca
    FOR EACH ROW EXECUTE FUNCTION fn_validar_presenca();

-- ---------------------------------------------------------------------
-- Auditoria: somente inserção
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_auditoria_somente_insercao() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'A auditoria é somente leitura: não pode ser alterada nem apagada.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auditoria_imutavel ON auditoria;
CREATE TRIGGER trg_auditoria_imutavel
    BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION fn_auditoria_somente_insercao();

DROP TRIGGER IF EXISTS trg_auditoria_sem_truncate ON auditoria;
CREATE TRIGGER trg_auditoria_sem_truncate
    BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION fn_auditoria_somente_insercao();

CREATE OR REPLACE FUNCTION fn_auditar() RETURNS trigger AS $$
DECLARE
    v_usuario BIGINT := NULLIF(current_setting('app.usuario_id', TRUE), '')::BIGINT;
    v_antes   JSONB;
    v_depois  JSONB;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_antes := to_jsonb(OLD) - 'password' - 'last_login';
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        v_depois := to_jsonb(NEW) - 'password' - 'last_login';
    END IF;

    -- UPDATE sem mudança real não gera histórico.
    IF TG_OP = 'UPDATE' AND v_antes = v_depois THEN
        RETURN NULL;
    END IF;

    INSERT INTO auditoria (usuario_id, tabela, registro_id, acao, valores_antes, valores_depois)
    VALUES (v_usuario,
            TG_TABLE_NAME,
            COALESCE(v_depois ->> 'id', v_antes ->> 'id')::BIGINT,
            TG_OP,
            v_antes,
            v_depois);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['usuario', 'crianca', 'sala', 'turma', 'matricula',
                             'realocacao', 'presenca', 'ocorrencia']
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS aud_%1$s ON %1$I', t);
        EXECUTE format(
            'CREATE TRIGGER aud_%1$s AFTER INSERT OR UPDATE OR DELETE ON %1$I '
            'FOR EACH ROW EXECUTE FUNCTION fn_auditar()', t);
    END LOOP;
END
$$;
