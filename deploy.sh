#!/usr/bin/env bash
# Despliega Finbot en Cloud Run desde el código fuente (Cloud Build construye la imagen).
#
# Uso:  PROJECT_ID=mi-proyecto bash deploy.sh
# Requisitos: gcloud auth login, un proyecto con facturación activa y permisos de editor.
# Si OPENAI_API_KEY está definida (en el entorno o en .env), se guarda en Secret Manager
# y se monta en el servicio; si no, Finbot funciona solo con reglas y glosario.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-southamerica-west1}"
SERVICE="${SERVICE:-finbot}"
SECRET="openai-api-key"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Falta PROJECT_ID: PROJECT_ID=mi-proyecto bash deploy.sh" >&2
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" && -f .env ]]; then
  OPENAI_API_KEY="$(grep -E '^OPENAI_API_KEY=' .env | cut -d= -f2- || true)"
fi
OPENAI_MODEL="${OPENAI_MODEL:-gpt-6-luna}"

echo "Proyecto: $PROJECT_ID · región: $REGION · servicio: $SERVICE"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "Habilitando APIs (la primera vez toma un par de minutos)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# En proyectos nuevos Cloud Build construye con esta cuenta; sin el rol builder no puede
# leer el código subido ni guardar la imagen en Artifact Registry.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" --role="roles/run.builder" \
  --condition=None >/dev/null

SECRET_FLAGS=()
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo "Guardando la clave de OpenAI en Secret Manager..."
  if gcloud secrets describe "$SECRET" >/dev/null 2>&1; then
    printf '%s' "$OPENAI_API_KEY" | gcloud secrets versions add "$SECRET" --data-file=- >/dev/null
  else
    printf '%s' "$OPENAI_API_KEY" | gcloud secrets create "$SECRET" --data-file=- >/dev/null
  fi
  # La cuenta de servicio por defecto de Cloud Run necesita leer el secreto.
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
  SECRET_FLAGS=(--update-secrets="OPENAI_API_KEY=${SECRET}:latest")
elif gcloud secrets versions describe latest --secret "$SECRET" >/dev/null 2>&1; then
  # La clave ya está en Secret Manager (por ejemplo, creada desde la consola): solo se conecta.
  echo "Usando la clave que ya está en Secret Manager ($SECRET)."
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
  SECRET_FLAGS=(--update-secrets="OPENAI_API_KEY=${SECRET}:latest")
else
  echo "Sin OPENAI_API_KEY: se despliega sin LLM (reglas y glosario)."
fi

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 \
  --min-instances 0 --max-instances 3 \
  --concurrency 80 --timeout 60 \
  --set-env-vars "OPENAI_MODEL=${OPENAI_MODEL}" \
  ${SECRET_FLAGS[@]+"${SECRET_FLAGS[@]}"} \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo
echo "Finbot publicado en: $URL"
echo "Prueba:  curl -s $URL/health"
