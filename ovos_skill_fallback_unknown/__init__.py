# Copyright 2017 Mycroft AI, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import re

from ovos_bus_client.message import Message
from ovos_workshop.skills.fallback import FallbackSkill
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators import fallback_handler


class UnknownSkill(FallbackSkill):

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(internet_before_load=False,
                                   network_before_load=False,
                                   gui_before_load=False,
                                   requires_internet=False,
                                   requires_network=False,
                                   requires_gui=False,
                                   no_internet_fallback=True,
                                   no_network_fallback=True,
                                   no_gui_fallback=True)

    def can_stop(self, message: Message) -> bool:
        return False

    def can_answer(self, message: Message) -> bool:
        return True
         
    def _longest_voc_match(self, utterance, voc_filename, at_start=False):
        """
        Return the length of the longest vocab entry from ``voc_filename``
        that matches ``utterance``, or -1 if none match.

        voc_match() only tells us whether *any* sample matched, not which
        one nor how long it was, so this uses voc_match_span() to let the
        caller compare match specificity across multiple vocab classes.
        With ``at_start``, only a match with no word before it counts.
        """
        hits = self.voc_match_span(utterance, voc_filename)
        if at_start:
            hits = [h for h in hits if not re.search(r"\w", utterance[:h[1]])]
        if not hits:
            return -1
        return max(end - start for _, start, end in hits)

    @fallback_handler(priority=100)
    def handle_fallback(self, message):
        utterance = message.data['utterance'].lower()
        # Evaluate all vocab classes and let the longest matched phrase win,
        # so a narrower phrase (eg. gl-ES "que é") doesn't shadow a longer,
        # more specific phrase that contains it (eg. "por que é"). Ties
        # are broken by the original fixed check order.
        # question_start.voc holds question words that, once accents are
        # folded, also spell a conjunction or relative pronoun (eg. gl-ES
        # "que"). They ask a question only when they open the utterance.
        lengths = {
            'question': max(self._longest_voc_match(utterance, 'question'),
                            self._longest_voc_match(utterance, 'question_start', at_start=True)),
            'who_is': self._longest_voc_match(utterance, 'who_is'),
            'why_is': self._longest_voc_match(utterance, 'why_is'),
        }
        best_type = None
        best_len = -1
        for i, match_len in lengths.items():
            if match_len > best_len:
                best_len = match_len
                best_type = i
        if best_type is not None and best_len >= 0:
            self.log.debug('Fallback type: ' + best_type)
            self.speak_dialog(best_type)
        else:
            self.speak_dialog('unknown')
