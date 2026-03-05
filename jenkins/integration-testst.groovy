pipeline {
    agent any

    stages {
        stage('Start Docker services') {
            steps {
                sh '''
                    set -e
                    docker compose down -v || true
                    docker compose up -d --build
                '''
            }
        }

        stage('Setup Python virtualenv') {
            steps {
                sh '''
                    set -e
                    cd api_gateway

                    # Создаём или переиспользуем окружение
                    python3 -m venv .venv
                    . .venv/bin/activate

                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Run integration tests') {
            steps {
                sh '''
                    set -e
                    cd api_gateway
                    . .venv/bin/activate

                    export GATEWAY_URL=http://host.docker.internal:8000
                    pytest -q test_integration_api_gateway.py -m integration
                '''
            }
        }
    }

    post {
        always {
            sh '''
                docker compose down -v || true
            '''
        }
    }
}

