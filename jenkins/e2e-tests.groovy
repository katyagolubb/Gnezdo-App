pipeline {
    agent any

    triggers {
        // Запуск по расписанию — каждый день в 03:00
        cron('0 3 * * *')
    }

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

        stage('Setup Node.js') {
            steps {
                sh '''
                    cd frontend
                    node --version
                    npm --version
                    npm install
                '''
            }
        }

        stage('Run E2E tests') {
            steps {
                sh '''
                    cd frontend
                    npm test -- --reporters=default --reporters=jest-junit
                '''
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'frontend/junit.xml'

            sh 'docker compose down -v || true'
        }

        success {
            echo 'E2E тесты прошли успешно!'
        }

        failure {
            echo 'E2E тесты упали. Проверьте отчёт.'
        }
    }
}
