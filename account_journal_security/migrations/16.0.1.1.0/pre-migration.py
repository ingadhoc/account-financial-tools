import odoo

#Caso de uso: quiero cambiar de nombre el campo user_ids por user_id
#Con Nico vimos usando la sentencia ALTER TABLE de SQL podemos hacer el cambio
# requerido de una forma fácil y eficiente sin tener que recurrir al método
# de openupgradelib. No estoy seguro si necesito agregar algo más dentro de
# este script ya que en el ejemplo donde vi que lo usaban lo estaba llamando
# desde otra función (era un módulo más complejo, quizás no fue el mejor ejemplo
# pero sirvió para sacar la sentencia SQL)
def migrate(cr, version):
    cr.execute("ALTER TABLE account_journal RENAME COLUMN user_ids TO user_id;")
