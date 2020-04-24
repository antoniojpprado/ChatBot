from django.test import TestCase

from core.models import Interaction


class InteractionTestCase(TestCase):
    def setUp(self):
        Interaction.objects.create(input='Command One',
                                   output='Relatório One',
                                   code='Sql',
                                   graph_labels='Título one')
        Interaction.objects.create(input='Command Two',
                                   output='Relatório Two',
                                   code='Command',
                                   graph_labels='Título two')

    def test_interation_structure(self):
        self.assertEqual(Interaction.objects.all().count(), 2)

        one = Interaction.objects.get(input="Command One")
        self.assertEqual(one.output, 'Relatório One')
        self.assertEqual(one.code, 'Sql')
        self.assertEqual(one.graph_labels, 'Título one')

        two = Interaction.objects.get(input="Command Two")
        self.assertEqual(two.output, 'Relatório Two')
        self.assertEqual(two.code, 'Command')
        self.assertEqual(two.graph_labels, 'Título two')
