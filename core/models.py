from django.db import models


class Interaction(models.Model):
    input = models.CharField(
        max_length=50,
        db_column="input",
        default='Informar',
        verbose_name="Input",
        help_text="Command name"
    )
    output = models.CharField(
        max_length=50,
        db_column="output",
        default='Informar',
        verbose_name="Output",
        help_text="Output message for user"
    )
    code = models.TextField(
        db_column="code",
        default='Informar',
        verbose_name="Code",
        help_text="Code or instruction to be execute"
    )
    graph_labels = models.CharField(
        max_length=100,
        db_column="graph_labels",
        default="title='Informar Título'\nxlabel='Informar Label x'\nylabel='Informar Label y'",
        verbose_name="Title and labels",
        help_text="Title and labels for graph"
    )
    type = models.CharField(
        max_length=30,
        db_column="type",
        default='Column',
        verbose_name="Type of interation",
        help_text="Graph and Table interation type"
    )

    def __str__(self):
        return self.input

    class Meta:
        db_table = "interaction"


class Contact(models.Model):
    user_id = models.CharField(
        max_length=20,
        db_column="user_id",
        verbose_name="User ID",
        help_text="User ID number in Telegram"
    )
    first_name = models.CharField(
        max_length=50,
        db_column="first_name",
        verbose_name="First Name",
        help_text="Contact first Name"
    )
    last_name = models.CharField(
        max_length=50,
        db_column="last_name",
        verbose_name="Last Name",
        help_text="Contact last name"
    )
    phone_number = models.CharField(
        max_length=20,
        db_column="phone_number",
        verbose_name="Phone Number",
        help_text="Contact phone number"
    )

    def __str__(self):
        return self.first_name

    class Meta:
        db_table = "contact"
