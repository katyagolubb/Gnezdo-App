pipeline {
    agent any

    stages {

        stage('Start Docker services') {
            steps {
                sh '''
                    docker compose down -v || true
                    docker compose up -d --build
                    sleep 20
                '''
            }
        }

        stage('Setup Python') {
            steps {
                sh '''
                    cd api_gateway
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Run integration tests') {
            steps {
                sh '''
                    cd api_gateway
                    . .venv/bin/activate

                    export GATEWAY_URL=http://host.docker.internal:8000

                    pytest -m integration \
                        --junitxml=report.xml \
                        --alluredir=allure-results
                '''
            }
        }
    }

    post {
        always {

            junit 'api_gateway/report.xml'

            allure([
                includeProperties: false,
                results: [[path: 'api_gateway/allure-results']]
            ])

            sh 'docker compose down -v || true'
        }
    }
}