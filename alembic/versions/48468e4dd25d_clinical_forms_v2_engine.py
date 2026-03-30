"""clinical_forms_v2_engine

Revision ID: 48468e4dd25d
Revises: 6c58fb09053f
Create Date: 2026-01-19 09:07:44.897498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '48468e4dd25d'
down_revision: Union[str, None] = '6c58fb09053f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enum types upfront
formstatus_enum = postgresql.ENUM('DRAFT', 'ACTIVE', 'ARCHIVED', name='formstatus', create_type=False)
targettype_enum = postgresql.ENUM('TODAS', 'EMBARAZADAS', 'POST_PARTO', 'MENOPAUSIA', 'LACTANCIA', 'DEPORTISTA', name='targettype', create_type=False)
frecuenciatype_enum = postgresql.ENUM('UNICA_VEZ', 'DIARIO', 'SEMANAL', 'MENSUAL', 'A_DEMANDA', name='frecuenciatype', create_type=False)
disparadortype_enum = postgresql.ENUM('AL_REGISTRO', 'BLOQUEANTE', 'MANUAL', 'DIA_7', 'DIA_30', name='disparadortype', create_type=False)
valuetype_enum = postgresql.ENUM('BOOL', 'INT', 'FLOAT', 'STRING', 'DATE', 'ARRAY', name='valuetype', create_type=False)
scoremode_enum = postgresql.ENUM('NONE', 'OPTION_SCORE', 'VALUE_AS_SCORE', 'FORMULA', name='scoremode', create_type=False)
uihint_enum = postgresql.ENUM('NUMERIC_KEYBOARD', 'SEARCHABLE_DROPDOWN', 'SLIDER_TICKS', 'TOP3_RANKING', 'YES_NO_BUTTONS', 'CHIPS_MULTI', name='uihint', create_type=False)
alerttype_enum = postgresql.ENUM('DERIVACION_CLINICA', 'ACTIVAR_PLAN', 'SEGUIMIENTO', name='alerttype', create_type=False)


def upgrade() -> None:
    # Create enum types first
    op.execute("CREATE TYPE formstatus AS ENUM ('DRAFT', 'ACTIVE', 'ARCHIVED')")
    op.execute("CREATE TYPE targettype AS ENUM ('TODAS', 'EMBARAZADAS', 'POST_PARTO', 'MENOPAUSIA', 'LACTANCIA', 'DEPORTISTA')")
    op.execute("CREATE TYPE frecuenciatype AS ENUM ('UNICA_VEZ', 'DIARIO', 'SEMANAL', 'MENSUAL', 'A_DEMANDA')")
    op.execute("CREATE TYPE disparadortype AS ENUM ('AL_REGISTRO', 'BLOQUEANTE', 'MANUAL', 'DIA_7', 'DIA_30')")
    op.execute("CREATE TYPE valuetype AS ENUM ('BOOL', 'INT', 'FLOAT', 'STRING', 'DATE', 'ARRAY')")
    op.execute("CREATE TYPE scoremode AS ENUM ('NONE', 'OPTION_SCORE', 'VALUE_AS_SCORE', 'FORMULA')")
    op.execute("CREATE TYPE uihint AS ENUM ('NUMERIC_KEYBOARD', 'SEARCHABLE_DROPDOWN', 'SLIDER_TICKS', 'TOP3_RANKING', 'YES_NO_BUTTONS', 'CHIPS_MULTI')")
    op.execute("CREATE TYPE alerttype AS ENUM ('DERIVACION_CLINICA', 'ACTIVAR_PLAN', 'SEGUIMIENTO')")
    
    # Create new tables
    op.create_table('scoring_rules',
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('form_id', sa.UUID(), nullable=False),
        sa.Column('variable_name', sa.String(), nullable=False),
        sa.Column('formula', sa.Text(), nullable=True),
        sa.Column('interpretation_ranges', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('alert_condition', sa.Text(), nullable=True),
        sa.Column('alert_type', alerttype_enum, nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['form_id'], ['clinical_forms.form_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('rule_id')
    )
    
    op.create_table('clinical_alerts',
        sa.Column('alert_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('submission_id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('alert_type', alerttype_enum, nullable=False),
        sa.Column('triggered_value', sa.Float(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(), nullable=True),
        sa.Column('is_viewed_admin', sa.Boolean(), nullable=True),
        sa.Column('is_shown_to_user', sa.Boolean(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['rule_id'], ['scoring_rules.rule_id']),
        sa.ForeignKeyConstraint(['submission_id'], ['user_submissions.submission_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('alert_id')
    )
    
    op.create_table('answer_options',
        sa.Column('option_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('label_key', sa.String(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['question_id'], ['form_questions.question_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('option_id')
    )
    
    # Add columns to clinical_forms
    op.add_column('clinical_forms', sa.Column('title_key', sa.String(), nullable=True))
    op.add_column('clinical_forms', sa.Column('description_key', sa.String(), nullable=True))
    op.add_column('clinical_forms', sa.Column('status', formstatus_enum, nullable=True))
    op.add_column('clinical_forms', sa.Column('target', targettype_enum, nullable=True))
    op.add_column('clinical_forms', sa.Column('frecuencia', frecuenciatype_enum, nullable=True))
    op.add_column('clinical_forms', sa.Column('disparador', disparadortype_enum, nullable=True))
    op.add_column('clinical_forms', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('clinical_forms', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    op.alter_column('clinical_forms', 'code', existing_type=sa.VARCHAR(), nullable=False)
    op.drop_constraint('clinical_forms_code_key', 'clinical_forms', type_='unique')
    op.create_index(op.f('ix_clinical_forms_code'), 'clinical_forms', ['code'], unique=True)
    
    # Add columns to form_questions
    op.add_column('form_questions', sa.Column('variable_name', sa.String(), nullable=True))  # Will update to not null after data migration
    op.add_column('form_questions', sa.Column('text_key', sa.String(), nullable=True))
    op.add_column('form_questions', sa.Column('value_type', valuetype_enum, nullable=True))
    op.add_column('form_questions', sa.Column('score_mode', scoremode_enum, nullable=True))
    op.add_column('form_questions', sa.Column('show_if', sa.Text(), nullable=True))
    op.add_column('form_questions', sa.Column('help_text', sa.Text(), nullable=True))
    op.add_column('form_questions', sa.Column('placeholder', sa.String(), nullable=True))
    op.add_column('form_questions', sa.Column('ui_hint', uihint_enum, nullable=True))
    op.add_column('form_questions', sa.Column('is_required', sa.Boolean(), nullable=True))
    op.add_column('form_questions', sa.Column('validation_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('form_questions', sa.Column('order_index', sa.Integer(), nullable=True))
    
    op.alter_column('form_questions', 'section_id', existing_type=sa.UUID(), nullable=False)
    op.alter_column('form_questions', 'type', existing_type=postgresql.ENUM('SINGLE_CHOICE', 'MULTIPLE_CHOICE', 'SCALE', 'TEXT', name='questiontype'), nullable=False)
    op.drop_constraint('form_questions_section_id_fkey', 'form_questions', type_='foreignkey')
    op.create_foreign_key(None, 'form_questions', 'form_sections', ['section_id'], ['section_id'], ondelete='CASCADE')
    
    # Add column to form_sections
    op.add_column('form_sections', sa.Column('bloque', sa.String(), nullable=True))
    op.alter_column('form_sections', 'form_id', existing_type=sa.UUID(), nullable=False)
    op.drop_constraint('form_sections_form_id_fkey', 'form_sections', type_='foreignkey')
    op.create_foreign_key(None, 'form_sections', 'clinical_forms', ['form_id'], ['form_id'], ondelete='CASCADE')
    
    # Add columns to submission_answers
    op.add_column('submission_answers', sa.Column('score', sa.Integer(), nullable=True))
    op.alter_column('submission_answers', 'submission_id', existing_type=sa.UUID(), nullable=False)
    op.alter_column('submission_answers', 'question_id', existing_type=sa.UUID(), nullable=False)
    op.drop_constraint('submission_answers_submission_id_fkey', 'submission_answers', type_='foreignkey')
    op.create_foreign_key(None, 'submission_answers', 'user_submissions', ['submission_id'], ['submission_id'], ondelete='CASCADE')
    
    # Add columns to user_submissions
    op.add_column('user_submissions', sa.Column('form_version', sa.Integer(), nullable=True))
    op.add_column('user_submissions', sa.Column('completed_at', sa.DateTime(), nullable=True))
    op.add_column('user_submissions', sa.Column('total_score', sa.Float(), nullable=True))
    op.add_column('user_submissions', sa.Column('score_interpretation', sa.String(), nullable=True))
    op.add_column('user_submissions', sa.Column('calculated_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.alter_column('user_submissions', 'user_id', existing_type=sa.UUID(), nullable=False)
    op.alter_column('user_submissions', 'form_id', existing_type=sa.UUID(), nullable=False)


def downgrade() -> None:
    # Drop columns from user_submissions
    op.alter_column('user_submissions', 'form_id', existing_type=sa.UUID(), nullable=True)
    op.alter_column('user_submissions', 'user_id', existing_type=sa.UUID(), nullable=True)
    op.drop_column('user_submissions', 'calculated_values')
    op.drop_column('user_submissions', 'score_interpretation')
    op.drop_column('user_submissions', 'total_score')
    op.drop_column('user_submissions', 'completed_at')
    op.drop_column('user_submissions', 'form_version')
    
    # Drop columns from submission_answers
    op.drop_constraint(None, 'submission_answers', type_='foreignkey')
    op.create_foreign_key('submission_answers_submission_id_fkey', 'submission_answers', 'user_submissions', ['submission_id'], ['submission_id'])
    op.alter_column('submission_answers', 'question_id', existing_type=sa.UUID(), nullable=True)
    op.alter_column('submission_answers', 'submission_id', existing_type=sa.UUID(), nullable=True)
    op.drop_column('submission_answers', 'score')
    
    # Drop columns from form_sections
    op.drop_constraint(None, 'form_sections', type_='foreignkey')
    op.create_foreign_key('form_sections_form_id_fkey', 'form_sections', 'clinical_forms', ['form_id'], ['form_id'])
    op.alter_column('form_sections', 'form_id', existing_type=sa.UUID(), nullable=True)
    op.drop_column('form_sections', 'bloque')
    
    # Drop columns from form_questions
    op.drop_constraint(None, 'form_questions', type_='foreignkey')
    op.create_foreign_key('form_questions_section_id_fkey', 'form_questions', 'form_sections', ['section_id'], ['section_id'])
    op.alter_column('form_questions', 'type', existing_type=postgresql.ENUM('SINGLE_CHOICE', 'MULTIPLE_CHOICE', 'SCALE', 'TEXT', name='questiontype'), nullable=True)
    op.alter_column('form_questions', 'section_id', existing_type=sa.UUID(), nullable=True)
    op.drop_column('form_questions', 'order_index')
    op.drop_column('form_questions', 'validation_rules')
    op.drop_column('form_questions', 'is_required')
    op.drop_column('form_questions', 'ui_hint')
    op.drop_column('form_questions', 'placeholder')
    op.drop_column('form_questions', 'help_text')
    op.drop_column('form_questions', 'show_if')
    op.drop_column('form_questions', 'score_mode')
    op.drop_column('form_questions', 'value_type')
    op.drop_column('form_questions', 'text_key')
    op.drop_column('form_questions', 'variable_name')
    
    # Drop columns from clinical_forms
    op.drop_index(op.f('ix_clinical_forms_code'), table_name='clinical_forms')
    op.create_unique_constraint('clinical_forms_code_key', 'clinical_forms', ['code'])
    op.alter_column('clinical_forms', 'code', existing_type=sa.VARCHAR(), nullable=True)
    op.drop_column('clinical_forms', 'updated_at')
    op.drop_column('clinical_forms', 'created_at')
    op.drop_column('clinical_forms', 'disparador')
    op.drop_column('clinical_forms', 'frecuencia')
    op.drop_column('clinical_forms', 'target')
    op.drop_column('clinical_forms', 'status')
    op.drop_column('clinical_forms', 'description_key')
    op.drop_column('clinical_forms', 'title_key')
    
    # Drop new tables
    op.drop_table('answer_options')
    op.drop_table('clinical_alerts')
    op.drop_table('scoring_rules')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS alerttype")
    op.execute("DROP TYPE IF EXISTS uihint")
    op.execute("DROP TYPE IF EXISTS scoremode")
    op.execute("DROP TYPE IF EXISTS valuetype")
    op.execute("DROP TYPE IF EXISTS disparadortype")
    op.execute("DROP TYPE IF EXISTS frecuenciatype")
    op.execute("DROP TYPE IF EXISTS targettype")
    op.execute("DROP TYPE IF EXISTS formstatus")
