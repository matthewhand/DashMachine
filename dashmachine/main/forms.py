from flask_wtf import FlaskForm
from wtforms import SelectField
from wtforms.fields.choices import SelectChoice


class TagsForm(FlaskForm):
    tags = SelectField(choices=[SelectChoice("All tags", "All tags")])
