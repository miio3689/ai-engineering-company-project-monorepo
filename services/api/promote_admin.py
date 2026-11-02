"""Promote an existing registered user without exposing a public endpoint."""

import argparse

from . import services_auth
from .models import EmailModel, UserRole, UserUpdate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email of the registered user to promote")
    arguments = parser.parse_args()
    try:
        email = EmailModel(email=arguments.email).email
        user = services_auth.obtener_usuario_por_email(email)
        if user is None:
            parser.error("No existe un usuario registrado con ese email.")
        promoted = services_auth.actualizar_usuario(
            user.id, UserUpdate(role=UserRole.admin)
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Usuario {promoted.email} promovido a admin (id={promoted.id}).")


if __name__ == "__main__":
    main()
