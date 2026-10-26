{{- define "sample-api.name" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "sample-api.selectorLabels" -}}
app.kubernetes.io/name: sample-api
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "sample-api.labels" -}}
{{ include "sample-api.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
aegis.io/environment: {{ .Values.environment | quote }}
{{- end -}}
