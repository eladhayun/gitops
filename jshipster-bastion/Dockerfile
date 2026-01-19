FROM ubuntu:22.04

# Set non-interactive mode
ENV DEBIAN_FRONTEND=noninteractive

# Install all required packages
RUN apt-get update && \
    apt-get install -y \
    postgresql-client \
    mysql-client \
    curl \
    netcat-openbsd \
    openssh-server \
    vim \
    git && \
    ln -sf /usr/bin/mysql /usr/bin/mariadb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create SSH directories
RUN mkdir -p /root/.ssh /var/run/sshd && \
    chmod 700 /root/.ssh

# Pre-configure SSH (will be overridden at runtime if needed)
RUN sed -i 's/^#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/^PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config && \
    sed -i 's/^PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config && \
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && \
    sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && \
    sed -i 's/^#AllowTcpForwarding.*/AllowTcpForwarding yes/' /etc/ssh/sshd_config && \
    sed -i 's/^AllowTcpForwarding.*/AllowTcpForwarding yes/' /etc/ssh/sshd_config

# Create entrypoint script
RUN echo '#!/bin/bash\n\
    set -e\n\
    # Copy SSH keys if they exist\n\
    if [ -f /tmp/ssh-keys/authorized_keys ]; then\n\
    cp /tmp/ssh-keys/authorized_keys /root/.ssh/authorized_keys &&\n\
    chmod 600 /root/.ssh/authorized_keys\n\
    fi\n\
    # Ensure SSH config is correct\n\
    grep -q "^PubkeyAuthentication yes" /etc/ssh/sshd_config || echo "PubkeyAuthentication yes" >> /etc/ssh/sshd_config\n\
    grep -q "^PermitRootLogin prohibit-password" /etc/ssh/sshd_config || echo "PermitRootLogin prohibit-password" >> /etc/ssh/sshd_config\n\
    grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config || echo "PasswordAuthentication no" >> /etc/ssh/sshd_config\n\
    grep -q "^AllowTcpForwarding yes" /etc/ssh/sshd_config || echo "AllowTcpForwarding yes" >> /etc/ssh/sshd_config\n\
    # Generate SSH host keys if they don'\''t exist\n\
    ssh-keygen -A\n\
    # Start SSH daemon\n\
    exec /usr/sbin/sshd -D\n\
    ' > /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
