# Security Group for EC2 instance
resource "aws_security_group" "ec2_sg" {
  name        = "${var.project_name}-ec2-sg-${var.environment}"
  description = "Security group for EC2 instance with Python web server"

  # Allow HTTP traffic
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }

  # Allow HTTPS traffic
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }

  # Allow SSH (optional, for debugging)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH"
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-ec2-sg-${var.environment}"
    Environment = var.environment
  }
}

# IAM Role for EC2 instance
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-ec2-role-${var.environment}"
    Environment = var.environment
  }
}

# Attach basic EC2 instance profile policy
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Instance profile for EC2
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile-${var.environment}"
  role = aws_iam_role.ec2_role.name
}

# User data script to install and run Python web server
locals {
  user_data = <<-EOF
#!/bin/bash
set -e  # Exit on error
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Starting user data script..."

# Update system (Amazon Linux 2023 uses dnf)
dnf update -y

# Install Python 3 and pip (usually pre-installed, but ensure it's there)
dnf install -y python3 python3-pip

# Verify Python and pip are installed
python3 --version
python3 -m pip --version

# Install Flask using python3 -m pip to ensure we use the correct pip
# Amazon Linux 2023 may require --break-system-packages flag
python3 -m pip install --upgrade pip --break-system-packages 2>&1 || python3 -m pip install --upgrade pip 2>&1
python3 -m pip install flask --break-system-packages 2>&1 || python3 -m pip install flask 2>&1

# Verify Flask is installed and can be imported
echo "Verifying Flask installation..."
if python3 -c "import flask; print(f'Flask version: {flask.__version__}')" 2>&1; then
    echo "Flask installed successfully at:"
    python3 -c "import flask; print(flask.__file__)"
else
    echo "ERROR: Flask installation verification failed!"
    echo "Python sys.path:"
    python3 -c "import sys; print('\n'.join(sys.path))" 2>&1
    echo "Searching for Flask:"
    find /usr -name flask -type d 2>/dev/null | head -5 || true
    find /usr/local -name flask -type d 2>/dev/null | head -5 || true
    echo "Trying to install Flask again with verbose output:"
    python3 -m pip install flask --break-system-packages -v 2>&1 | tail -20
    exit 1
fi

# Create web server directory
mkdir -p /var/www/app
cd /var/www/app

# Create Python web server script
cat > app.py << 'PYTHON_EOF'
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello_world():
    return jsonify({
        'message': 'Hello World!',
        'status': 'success'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
PYTHON_EOF

# Find the correct python3 path
PYTHON3_PATH=$(which python3)
echo "Python3 path: $PYTHON3_PATH"

# Get Python site-packages paths for PYTHONPATH
PYTHON_SITE_PACKAGES=$(python3 -c "import site; print(':'.join(site.getsitepackages()))" 2>/dev/null || echo "/usr/local/lib/python3.11/site-packages:/usr/lib/python3.11/site-packages")
echo "Python site-packages: $PYTHON_SITE_PACKAGES"

# Create systemd service file with proper PYTHONPATH
# Using printf to properly handle variable expansion
cat > /tmp/flask-app.service << 'SERVICETEMPLATE'
[Unit]
Description=Flask Hello World App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/app
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=PYTHONPATH_PLACEHOLDER"
ExecStart=/usr/bin/python3 /var/www/app/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICETEMPLATE

# Replace placeholder with actual PYTHONPATH
sed "s|PYTHONPATH_PLACEHOLDER|${PYTHON_SITE_PACKAGES}|g" /tmp/flask-app.service > /etc/systemd/system/flask-app.service
rm /tmp/flask-app.service

# Verify Flask is still accessible before starting service
python3 -c "import flask" || {
    echo "ERROR: Flask not found before starting service!"
    exit 1
}

# Enable and start the service
systemctl daemon-reload
systemctl enable flask-app

# Wait a moment before starting
sleep 2
systemctl start flask-app

# Wait a moment and check status
sleep 5
if systemctl is-active --quiet flask-app; then
    echo "Flask service started successfully"
    systemctl status flask-app --no-pager -n 20 || true
else
    echo "ERROR: Flask service failed to start"
    systemctl status flask-app --no-pager -n 50 || true
    exit 1
fi

# Check if port 80 is listening
echo "Checking if port 80 is listening..."
ss -tlnp | grep :80 || netstat -tlnp | grep :80 || echo "Port 80 not yet listening (may take a few more seconds)"

echo "User data script completed"
EOF
}

# EC2 Instance
resource "aws_instance" "web_server" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro"
  subnet_id              = data.aws_subnet.default.id
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  user_data              = base64encode(local.user_data)
  
  # Enable public IP
  associate_public_ip_address = true

  tags = {
    Name        = "${var.project_name}-web-server-${var.environment}"
    Environment = var.environment
  }
}

# Get the default VPC
data "aws_vpc" "default" {
  default = true
}

# Get the first available subnet in the default VPC
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_subnet" "default" {
  id = data.aws_subnets.default.ids[0]
}

# Get the latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Output the EC2 instance public IP
output "ec2_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.web_server.public_ip
}

# Output the EC2 instance public DNS
output "ec2_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = aws_instance.web_server.public_dns
}

# Output the hello world endpoint URL
output "hello_world_url" {
  description = "URL to access the hello world endpoint"
  value       = "http://${aws_instance.web_server.public_ip}"
}

# Output the EC2 instance ID for debugging
output "ec2_instance_id" {
  description = "EC2 instance ID for debugging"
  value       = aws_instance.web_server.id
}

