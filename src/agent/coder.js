import { writeFile, readFile, mkdirSync } from 'fs';
import { makeCompartment, lockdown } from './library/lockdown.js';
import * as skills from './library/skills.js';
import * as world from './library/world.js';
import { Vec3 } from 'vec3';
import {ESLint} from "eslint";

export class Coder {
    constructor(agent) {
        this.agent = agent;
        this.file_counter = 0;
        this.fp = '/bots/'+agent.name+'/action-code/';
        this.code_template = '';
        this.code_lint_template = '';

        readFile('./bots/execTemplate.js', 'utf8', (err, data) => {
            if (err) throw err;
            this.code_template = data;
        });
        readFile('./bots/lintTemplate.js', 'utf8', (err, data) => {
            if (err) throw err;
            this.code_lint_template = data;
        });
        mkdirSync('.' + this.fp, { recursive: true });
    }

    async generateCode(agent_history) {
        this.agent.bot.modes.pause('unstuck');
        lockdown();
        let messages = agent_history.getHistory(); 
        messages.push({role: 'system', content: 'Code generation started. Write code in codeblock in your response:'});

        const MAX_ATTEMPTS = 5;
        const MAX_NO_CODE = 3;

        console.log(`[coder] generateCode started (file_counter=${this.file_counter}, ` +
            `interrupt=${this.agent.bot.interrupt_code}, history_len=${messages.length})`);

        let code = null;
        let no_code_failures = 0;
        for (let i=0; i<MAX_ATTEMPTS; i++) {
            if (this.agent.bot.interrupt_code) {
                console.warn(`[coder] generateCode aborted before attempt ${i+1}: interrupt_code is true`);
                return null;
            }
            console.log(`[coder] attempt ${i+1}/${MAX_ATTEMPTS} — calling promptCoding...`);
            const messages_copy = JSON.parse(JSON.stringify(messages));
            let res = await this.agent.prompter.promptCoding(messages_copy);
            if (this.agent.bot.interrupt_code) {
                console.warn(`[coder] generateCode interrupted after promptCoding (attempt ${i+1})`);
                return null;
            }
            let contains_code = res.indexOf('```') !== -1;
            if (!contains_code) {
                if (res.indexOf('!newAction') !== -1) {
                    console.warn(`[coder] attempt ${i+1}: coding response contained !newAction instead of code, retrying`);
                    messages.push({
                        role: 'assistant', 
                        content: res.substring(0, res.indexOf('!newAction'))
                    });
                    continue;
                }
                
                no_code_failures++;
                console.warn(`[coder] attempt ${i+1}: no code block in response (no_code_failures=${no_code_failures}/${MAX_NO_CODE})`);
                if (no_code_failures >= MAX_NO_CODE) {
                    console.warn("[coder] generateCode failed: agent would not write code");
                    return 'Action failed, agent would not write code.';
                }
                messages.push({
                    role: 'system', 
                    content: 'Error: no code provided. Write code in codeblock in your response. ``` // example ```'}
                );
                continue;
            }
            code = res.substring(res.indexOf('```')+3, res.lastIndexOf('```'));

            let result;
            try {
                result = await this._stageCode(code);
            } catch (e) {
                console.error(`[coder] attempt ${i+1}: _stageCode threw: ${e}`);
                return 'Failed to stage code: ' + e.toString();
            }

            const executionModule = result.func;
            const lintResult = await this._lintCode(result.src_lint_copy);
            if (lintResult) {
                const message = 'Error: Code lint error:'+'\n'+lintResult+'\nPlease try again.';
                console.warn(`[coder] attempt ${i+1}: lint error`);
                messages.push({ role: 'system', content: message });
                continue;
            }
            if (!executionModule) {
                console.warn("[coder] generateCode failed: executionModule is null after staging");
                return 'Failed to stage code, something is wrong.';
            }

            try {
                console.log(`[coder] attempt ${i+1}: executing code...`);
                await executionModule.main(this.agent.bot);

                const code_output = this.agent.actions.getBotOutputSummary();
                const summary = "Agent wrote this code: \n```" + this._sanitizeCode(code) + "```\nCode Output:\n" + code_output;
                console.log(`[coder] attempt ${i+1}: code execution succeeded`);
                return summary;
            } catch (e) {
                if (this.agent.bot.interrupt_code) {
                    console.warn(`[coder] attempt ${i+1}: code execution interrupted`);
                    return null;
                }
                
                console.warn(`[coder] attempt ${i+1}: code execution threw: ${e}`);

                const code_output = this.agent.actions.getBotOutputSummary();

                messages.push({
                    role: 'assistant',
                    content: res
                });
                messages.push({
                    role: 'system',
                    content: `Code Output:\n${code_output}\nCODE EXECUTION THREW ERROR: ${e.toString()}\n Please try again:`
                });
            }
        }
        console.warn(`[coder] generateCode failed: all ${MAX_ATTEMPTS} attempts exhausted`);
        return `Code generation failed after ${MAX_ATTEMPTS} attempts.`;
    }
    
    async  _lintCode(code) {
        let result = '#### CODE ERROR INFO ###\n';
        // Extract everything in the code between the beginning of 'skills./world.' and the '('
        const skillRegex = /(?:skills|world)\.(.*?)\(/g;
        const skills = [];
        let match;
        while ((match = skillRegex.exec(code)) !== null) {
            skills.push(match[1]);
        }
        const allDocs = await this.agent.prompter.skill_libary.getAllSkillDocs();
        // check function exists
        const missingSkills = skills.filter(skill => !!allDocs[skill]);
        if (missingSkills.length > 0) {
            result += 'These functions do not exist.\n';
            result += '### FUNCTIONS NOT FOUND ###\n';
            result += missingSkills.join('\n');
            console.log(result)
            return result;
        }

        const eslint = new ESLint();
        const results = await eslint.lintText(code);
        const codeLines = code.split('\n');
        const exceptions = results.map(r => r.messages).flat();

        if (exceptions.length > 0) {
            exceptions.forEach((exc, index) => {
                if (exc.line && exc.column ) {
                    const errorLine = codeLines[exc.line - 1]?.trim() || 'Unable to retrieve error line content';
                    result += `#ERROR ${index + 1}\n`;
                    result += `Message: ${exc.message}\n`;
                    result += `Location: Line ${exc.line}, Column ${exc.column}\n`;
                    result += `Related Code Line: ${errorLine}\n`;
                }
            });
            result += 'The code contains exceptions and cannot continue execution.';
        } else {
            return null;//no error
        }

        return result ;
    }
    // write custom code to file and import it
    // write custom code to file and prepare for evaluation
    async _stageCode(code) {
        code = this._sanitizeCode(code);
        let src = '';
        code = code.replaceAll('console.log(', 'log(bot,');
        code = code.replaceAll('log("', 'log(bot,"');

        console.log(`Generated code: """${code}"""`);

        code = code.replaceAll(';\n', '; if(bot.interrupt_code) {log(bot, "Code interrupted.");return;}\n');
        for (let line of code.split('\n')) {
            src += `    ${line}\n`;
        }
        let src_lint_copy = this.code_lint_template.replace('/* CODE HERE */', src);
        src = this.code_template.replace('/* CODE HERE */', src);

        let filename = this.file_counter + '.js';
        this.file_counter++;
        
        const filePath = '.' + this.fp + filename;
        try {
            await this._writeFilePromise(filePath, src);
            console.log(`[coder] wrote action file: ${filePath}`);
        } catch (e) {
            console.error(`[coder] failed to write ${filePath}: ${e}`);
            throw e;
        }

        let mainFn;
        try {
            const compartment = makeCompartment({
                skills,
                log: skills.log,
                world,
                Vec3,
            });
            mainFn = compartment.evaluate(src);
        } catch (e) {
            console.error(`[coder] compartment.evaluate failed for ${filename}: ${e}`);
            throw e;
        }

        return { func:{main: mainFn}, src_lint_copy: src_lint_copy };
    }

    _sanitizeCode(code) {
        code = code.trim();
        const remove_strs = ['Javascript', 'javascript', 'js']
        for (let r of remove_strs) {
            if (code.startsWith(r)) {
                code = code.slice(r.length);
                return code;
            }
        }
        return code;
    }

    _writeFilePromise(filename, src) {
        // makes it so we can await this function
        return new Promise((resolve, reject) => {
            writeFile(filename, src, (err) => {
                if (err) {
                    reject(err);
                } else {
                    resolve();
                }
            });
        });
    }
}